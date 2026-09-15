"""Orquestrador do pipeline medalhao.

Executa as etapas na ordem bronze -> silver -> integracao -> validacao -> gold
-> qualidade.
Cada etapa mora no modulo do seu responsavel; este arquivo so chama, cronometra
e registra o que saiu.

As etapas sao desenvolvidas em paralelo pelos quatro membros, entao o pipeline
precisa rodar com as seguintes ainda ausentes: etapa cujo modulo nao existe e
anunciada e pulada, e a execucao segue. Isso vale apenas para o modulo nao
existir -- erro dentro de uma etapa que existe sobe e derruba o pipeline, como
tem de ser.

Uso:

    python -m src.run_pipeline                  # tudo, na ordem
    python -m src.run_pipeline --etapa bronze   # so uma etapa
    python -m src.run_pipeline --ate silver     # da primeira ate essa
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq

RAIZ = Path(__file__).resolve().parents[1]
DIR_BRONZE = RAIZ / "data" / "bronze"
DIR_SILVER = RAIZ / "data" / "silver"
DIR_GOLD = RAIZ / "data" / "gold"

logger = logging.getLogger("pipeline")


@dataclass(frozen=True)
class Etapa:
    """Uma etapa do medalhao e onde ela escreve."""

    nome: str
    modulo: str
    dono: str
    saidas: tuple[Path, ...]


# Os nomes de modulo seguem a estrutura anunciada no README. Cada etapa expoe
# `executar()` ou, na falta dela, `main()`.
ETAPAS: tuple[Etapa, ...] = (
    Etapa("bronze", "src.bronze.ingest", "membro 1", (DIR_BRONZE,)),
    Etapa("silver", "src.silver.transform", "membro 2", (DIR_SILVER,)),
    Etapa("integracao", "src.silver.integracao_municipios", "membro 3", (DIR_SILVER,)),
    # Roda antes da gold de proposito: a gold so deve montar as fatos sobre
    # camadas que passaram na validacao. Reprovacao aqui derruba o pipeline.
    Etapa("validacao", "src.qualidade.validar_camadas", "qualidade", (DIR_SILVER,)),
    Etapa("gold", "src.gold.dimensional", "membro 4", (DIR_GOLD,)),
    Etapa("qualidade", "src.gold.qualidade", "membro 4", (DIR_GOLD,)),
)


@dataclass
class ResultadoEtapa:
    """O que uma etapa produziu, para o resumo final."""

    nome: str
    situacao: str                      # executada | pulada
    duracao_s: float = 0.0
    tabelas: list[tuple[str, int | None, int]] = field(default_factory=list)


def formatar(n: int | None) -> str:
    return "?" if n is None else f"{n:,}".replace(",", ".")


def inventariar(diretorios: tuple[Path, ...]) -> dict[Path, tuple[int, int]]:
    """Fotografa os arquivos de saida: caminho -> (mtime, linhas).

    Comparar a foto de antes com a de depois e o que permite listar as tabelas
    que a etapa gerou sem depender do que ela devolve.
    """
    foto: dict[Path, tuple[int, int]] = {}
    for diretorio in diretorios:
        if not diretorio.exists():
            continue
        for caminho in sorted(diretorio.glob("*.parquet")):
            foto[caminho] = (caminho.stat().st_mtime_ns, pq.ParquetFile(caminho).metadata.num_rows)
        for caminho in sorted(diretorio.glob("*.duckdb")):
            foto[caminho] = (caminho.stat().st_mtime_ns, -1)
    return foto


def tabelas_do_retorno(retorno: object) -> list[tuple[str, int | None, int]]:
    """Le contagens de entrada e saida do que a etapa devolveu, se devolveu algo.

    Convencao, nao exigencia: uma etapa que devolve itens com `tabela`,
    `linhas_entrada` e `linhas_saida` (a bronze devolve) tem as duas contagens
    no log. Quem nao devolver nada cai no inventario de arquivos, que so
    enxerga a contagem de saida.
    """
    if not isinstance(retorno, (list, tuple)):
        return []
    tabelas = []
    for item in retorno:
        if isinstance(item, dict):
            nome = item.get("tabela")
            entrada, saida = item.get("linhas_entrada"), item.get("linhas_saida")
        else:
            nome = getattr(item, "tabela", None)
            entrada = getattr(item, "linhas_entrada", None)
            saida = getattr(item, "linhas_saida", None)
        if nome is not None and saida is not None:
            tabelas.append((str(nome), entrada, int(saida)))
    return tabelas


def tabelas_do_inventario(
    antes: dict[Path, tuple[int, int]], depois: dict[Path, tuple[int, int]]
) -> list[tuple[str, int | None, int]]:
    """Arquivos criados ou reescritos pela etapa, com a contagem de linhas."""
    return [
        (caminho.name, None, linhas)
        for caminho, (_, linhas) in sorted(depois.items())
        if antes.get(caminho) != (depois[caminho])
    ]


def resolver_entrada(modulo) -> tuple[str, object]:
    for nome in ("executar", "main"):
        funcao = getattr(modulo, nome, None)
        if callable(funcao):
            return nome, funcao
    raise AttributeError(
        f"O modulo {modulo.__name__} nao expoe executar() nem main(). "
        "O orquestrador chama uma das duas."
    )


def executar_etapa(etapa: Etapa) -> ResultadoEtapa:
    # find_spec separa as duas situacoes que um ModuleNotFoundError misturaria:
    # o modulo da etapa ainda nao foi escrito (pula) ou o modulo existe e uma
    # dependencia dele falta (erro de verdade, que precisa aparecer).
    if importlib.util.find_spec(etapa.modulo) is None:
        logger.warning(
            "etapa %s (%s): modulo %s ainda nao existe -- etapa pulada, o pipeline segue",
            etapa.nome, etapa.dono, etapa.modulo,
        )
        return ResultadoEtapa(etapa.nome, "pulada")

    # O cabecalho vem antes do import: se o modulo da etapa quebrar ao ser
    # importado, o log ja diz de quem e a etapa que falhou.
    logger.info("-" * 78)
    logger.info(
        "etapa %s (%s) | %s | inicio %s",
        etapa.nome, etapa.dono, etapa.modulo, datetime.now().strftime("%H:%M:%S"),
    )
    modulo = importlib.import_module(etapa.modulo)
    nome_funcao, funcao = resolver_entrada(modulo)
    logger.info("etapa %s: chamando %s.%s()", etapa.nome, etapa.modulo, nome_funcao)
    antes = inventariar(etapa.saidas)
    inicio = time.perf_counter()
    try:
        retorno = funcao()
    except Exception:
        # Nao engole nada: registra em qual etapa quebrou e deixa subir.
        logger.error("etapa %s falhou apos %.2fs", etapa.nome, time.perf_counter() - inicio)
        raise
    duracao = time.perf_counter() - inicio
    depois = inventariar(etapa.saidas)

    tabelas = tabelas_do_retorno(retorno) or tabelas_do_inventario(antes, depois)
    logger.info("etapa %s concluida em %.2fs | %d tabela(s)", etapa.nome, duracao, len(tabelas))
    for nome, entrada, saida in tabelas:
        logger.info(
            "   %-30s entrada %12s -> saida %12s",
            nome, formatar(entrada), formatar(saida),
        )
    return ResultadoEtapa(etapa.nome, "executada", duracao, tabelas)


def selecionar(etapa: str | None, ate: str | None) -> list[Etapa]:
    if etapa:
        return [e for e in ETAPAS if e.nome == etapa]
    if ate:
        nomes = [e.nome for e in ETAPAS]
        return list(ETAPAS[: nomes.index(ate) + 1])
    return list(ETAPAS)


def executar(etapa: str | None = None, ate: str | None = None) -> list[ResultadoEtapa]:
    selecionadas = selecionar(etapa, ate)
    logger.info("pipeline iniciado %s | etapas: %s",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ", ".join(e.nome for e in selecionadas))

    inicio = time.perf_counter()
    resultados = [executar_etapa(e) for e in selecionadas]
    total = time.perf_counter() - inicio

    logger.info("-" * 78)
    logger.info("resumo do pipeline (%.2fs no total)", total)
    for resultado in resultados:
        linhas = sum(saida for _, _, saida in resultado.tabelas if saida >= 0)
        logger.info(
            "   %-12s %-10s %7.2fs  %2d tabela(s)  %12s linhas",
            resultado.nome, resultado.situacao, resultado.duracao_s,
            len(resultado.tabelas), formatar(linhas),
        )
    return resultados


def main() -> None:
    analisador = argparse.ArgumentParser(
        prog="python -m src.run_pipeline",
        description="Executa o pipeline medalhao do DW de e-commerce.",
    )
    grupo = analisador.add_mutually_exclusive_group()
    nomes = [e.nome for e in ETAPAS]
    grupo.add_argument("--etapa", choices=nomes, help="executa somente esta etapa")
    grupo.add_argument("--ate", choices=nomes, help="executa da primeira etapa ate esta")
    argumentos = analisador.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    executar(argumentos.etapa, argumentos.ate)


if __name__ == "__main__":
    main()
