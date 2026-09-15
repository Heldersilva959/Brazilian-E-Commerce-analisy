"""Obtencao das fontes publicas do IBGE usadas pelo projeto.

Baixa e grava, sem alterar o conteudo recebido:

* `data/raw/ibge/municipios.json` -- cadastro de municipios (IBGE Localidades).
* `data/raw/socioeconomico/originais/sidra_6579_populacao_estimada_2017.json`
* `data/raw/socioeconomico/originais/sidra_5938_pib_2017.json`

A partir das duas exportacoes do SIDRA, monta
`data/raw/socioeconomico/indicadores_municipais.csv` no contrato descrito no
README. Cada arquivo original recebe um `.meta.json` com URL, data de obtencao,
tamanho e SHA-256, para auditoria.

Execucao:

    .venv/Scripts/python.exe src/utils/baixar_fontes_ibge.py
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DIR_IBGE = RAIZ / "data" / "raw" / "ibge"
DIR_SOCIO = RAIZ / "data" / "raw" / "socioeconomico"
DIR_ORIGINAIS = DIR_SOCIO / "originais"

URL_MUNICIPIOS = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
# Tabela 6579, variavel 9324 (Populacao residente estimada, em pessoas),
# nivel N6 (municipios), periodo 2017.
URL_SIDRA_POPULACAO = "https://apisidra.ibge.gov.br/values/t/6579/n6/all/v/9324/p/2017"
# Tabela 5938, variavel 37 (PIB a precos correntes, em Mil Reais),
# nivel N6 (municipios), periodo 2017.
URL_SIDRA_PIB = "https://apisidra.ibge.gov.br/values/t/5938/n6/all/v/37/p/2017"

ANO_REFERENCIA = 2017
# Marcadores de ausencia usados pelo SIDRA; viram celula vazia no consolidado.
AUSENTES = {"", "-", "..", "...", "X", "x"}

log = logging.getLogger("fontes_ibge")


def _baixar(url: str) -> bytes:
    requisicao = urllib.request.Request(
        url,
        headers={
            "User-Agent": "dw-olist-ibge/1.0 (trabalho academico)",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        },
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=300) as resposta:
            conteudo = resposta.read()
    except (urllib.error.URLError, TimeoutError) as erro:
        raise RuntimeError(f"Falha ao obter {url}: {erro}") from erro
    if conteudo[:2] == b"\x1f\x8b":
        conteudo = gzip.decompress(conteudo)
    return conteudo


def _gravar_original(destino: Path, url: str, conteudo: bytes) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(conteudo)
    meta = {
        "url": url,
        "arquivo": destino.name,
        "data_obtencao": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bytes": len(conteudo),
        "sha256": hashlib.sha256(conteudo).hexdigest(),
    }
    destino.with_suffix(destino.suffix + ".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log.info("gravado %s (%d bytes)", destino.relative_to(RAIZ), len(conteudo))


def _obter(destino: Path, url: str) -> bytes:
    """Reutiliza o arquivo ja gravado; so acessa a rede quando ele nao existe."""
    if destino.exists():
        log.info("cache reutilizado: %s", destino.relative_to(RAIZ))
        return destino.read_bytes()
    conteudo = _baixar(url)
    json.loads(conteudo)  # aborta cedo se a resposta nao for JSON valido
    _gravar_original(destino, url, conteudo)
    return conteudo


def _valores_sidra(conteudo: bytes, rotulo: str) -> dict[str, str]:
    """Le uma resposta do apisidra e devolve {codigo municipal: valor}.

    A primeira linha da resposta traz os rotulos das colunas, nao dados.
    """
    linhas = json.loads(conteudo)
    if len(linhas) < 2:
        raise RuntimeError(f"Resposta do SIDRA sem dados para {rotulo}.")
    valores: dict[str, str] = {}
    for linha in linhas[1:]:
        codigo = linha["D1C"]
        ano = linha["D3C"]
        if ano != str(ANO_REFERENCIA):
            raise RuntimeError(f"{rotulo}: ano inesperado {ano} em {codigo}.")
        if codigo in valores:
            raise RuntimeError(f"{rotulo}: codigo duplicado {codigo}.")
        bruto = str(linha["V"]).strip()
        valores[codigo] = "" if bruto in AUSENTES else bruto
    log.info("%s: %d municipios lidos", rotulo, len(valores))
    return valores


def _consolidar(populacao: dict[str, str], pib_mil_reais: dict[str, str]) -> Path:
    codigos = sorted(set(populacao) | set(pib_mil_reais))
    destino = DIR_SOCIO / "indicadores_municipais.csv"
    sem_pop = sem_pib = sem_per_capita = 0

    with destino.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo, lineterminator="\n")
        escritor.writerow(
            ["cod_ibge", "ano_referencia", "populacao_estimada", "pib_per_capita"]
        )
        for codigo in codigos:
            pop = populacao.get(codigo, "")
            pib = pib_mil_reais.get(codigo, "")
            sem_pop += not pop
            sem_pib += not pib
            # PIB per capita em reais por habitante: o SIDRA nao publica esse
            # indicador, entao ele e derivado do PIB em Mil Reais dividido pela
            # populacao estimada do mesmo ano, como faz o proprio IBGE.
            if pop and pib and int(pop) > 0:
                per_capita = f"{int(pib) * 1000 / int(pop):.2f}"
            else:
                per_capita = ""
                sem_per_capita += 1
            escritor.writerow([codigo, ANO_REFERENCIA, pop, per_capita])

    log.info(
        "consolidado %s: %d municipios, %d sem populacao, %d sem PIB, "
        "%d sem PIB per capita",
        destino.relative_to(RAIZ),
        len(codigos),
        sem_pop,
        sem_pib,
        sem_per_capita,
    )
    return destino


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    DIR_IBGE.mkdir(parents=True, exist_ok=True)
    DIR_ORIGINAIS.mkdir(parents=True, exist_ok=True)

    municipios = json.loads(_obter(DIR_IBGE / "municipios.json", URL_MUNICIPIOS))
    log.info("IBGE Localidades: %d municipios no cadastro atual", len(municipios))

    populacao = _valores_sidra(
        _obter(
            DIR_ORIGINAIS / "sidra_6579_populacao_estimada_2017.json",
            URL_SIDRA_POPULACAO,
        ),
        "populacao estimada (tabela 6579)",
    )
    pib = _valores_sidra(
        _obter(DIR_ORIGINAIS / "sidra_5938_pib_2017.json", URL_SIDRA_PIB),
        "PIB a precos correntes (tabela 5938)",
    )
    _consolidar(populacao, pib)


if __name__ == "__main__":
    main()
