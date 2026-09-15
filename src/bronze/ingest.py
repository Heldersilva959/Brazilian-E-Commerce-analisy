"""Camada bronze: ingestao fiel das fontes de `data/raw/` para Parquet.

Regra da camada, conforme a secao 3 do contrato de dados: copia literal. Toda
coluna de dado vira VARCHAR, string vazia continua string vazia, nenhuma linha
e filtrada, deduplicada ou descartada. A conversao de '' para NULL, a tipagem e
a limpeza sao da silver.

Cada tabela recebe quatro colunas de linhagem: `_fonte`, `_arquivo_origem`,
`_data_ingestao` e `_linha_origem`. As duas ultimas tem tipo proprio
(TIMESTAMP e BIGINT) porque sao metadado da ingestao, nao dado da fonte.

As decisoes de leitura abaixo saem de medicao feita nos arquivos reais e
registrada em `docs/inventario_fontes.md`, secao 5.

Execucao isolada, sem passar pelo orquestrador:

    python -m src.bronze.ingest
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

RAIZ = Path(__file__).resolve().parents[2]
DIR_BRUTO = RAIZ / "data" / "raw"
DIR_BRONZE = RAIZ / "data" / "bronze"
CAMINHO_MANIFESTO = DIR_BRONZE / "_manifesto.json"

# Campos de comentario de avaliacao passam de 8 mil caracteres; o limite padrao
# do modulo csv nao da conta na contagem de conferencia.
csv.field_size_limit(10_000_000)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FonteCSV:
    """Uma fonte CSV e a tabela bronze que ela alimenta."""

    tabela: str          # nome do parquet de saida, sem extensao
    origem: str          # caminho relativo a data/raw/
    fonte: str           # valor da coluna _fonte
    onde_obter: str      # instrucao exibida quando o arquivo nao existe


FONTES_CSV: tuple[FonteCSV, ...] = (
    FonteCSV(
        tabela="olist_pedidos",
        origem="olist/olist_orders_dataset.csv",
        fonte="olist",
        onde_obter="dataset 'Brazilian E-Commerce Public Dataset by Olist', no Kaggle",
    ),
    FonteCSV(
        tabela="olist_itens_pedido",
        origem="olist/olist_order_items_dataset.csv",
        fonte="olist",
        onde_obter="dataset 'Brazilian E-Commerce Public Dataset by Olist', no Kaggle",
    ),
    FonteCSV(
        tabela="olist_clientes",
        origem="olist/olist_customers_dataset.csv",
        fonte="olist",
        onde_obter="dataset 'Brazilian E-Commerce Public Dataset by Olist', no Kaggle",
    ),
)


@dataclass
class ResultadoIngestao:
    """O que uma tabela produziu, para o log do orquestrador."""

    tabela: str
    arquivo_origem: str
    caminho_saida: Path
    linhas_entrada: int
    linhas_saida: int
    colunas_dados: int
    data_ingestao: datetime
    fonte_alterada: bool
    sha256: str
    duracao_s: float


class FonteAusenteError(FileNotFoundError):
    """Arquivo de origem esperado pelo contrato nao esta em data/raw/."""


class ContagemDivergenteError(RuntimeError):
    """Saida com numero de linhas diferente da origem -- bug de ingestao."""


def sha256_arquivo(caminho: Path) -> str:
    digestor = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            digestor.update(bloco)
    return digestor.hexdigest()


def carregar_manifesto() -> dict:
    """Le o manifesto da execucao anterior; ausente, comeca vazio."""
    if not CAMINHO_MANIFESTO.exists():
        return {"versao": 1, "fontes": {}}
    manifesto = json.loads(CAMINHO_MANIFESTO.read_text(encoding="utf-8"))
    manifesto.setdefault("fontes", {})
    return manifesto


def gravar_manifesto(manifesto: dict) -> None:
    CAMINHO_MANIFESTO.write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def exigir_fonte(fonte: FonteCSV) -> Path:
    """Devolve o caminho da origem ou falha dizendo qual arquivo falta e onde."""
    caminho = DIR_BRUTO / fonte.origem
    if caminho.exists():
        return caminho
    raise FonteAusenteError(
        "Fonte da bronze nao encontrada.\n"
        f"  Tabela afetada : {fonte.tabela}\n"
        f"  Arquivo        : {Path(fonte.origem).name}\n"
        f"  Caminho exigido: {caminho}\n"
        f"  Onde obter     : {fonte.onde_obter}\n"
        "A bronze nao gera dado sintetico nem pula arquivo: coloque o arquivo "
        "no caminho acima e execute de novo."
    )


def contar_registros(caminho: Path) -> int:
    """Conta registros do CSV, sem contar o cabecalho.

    Conferencia independente da leitura do pandas: e ela que prova o criterio
    de aceite de contagem identica. Registro nao e o mesmo que linha fisica --
    `olist_order_reviews_dataset.csv` tem 3.852 registros com quebra de linha
    dentro do campo de comentario.
    """
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.reader(arquivo)
        next(leitor)  # cabecalho
        return sum(1 for _ in leitor)


def ler_csv_como_texto(caminho: Path) -> pd.DataFrame:
    """Le o CSV inteiro como texto, preservando o que esta no arquivo.

    `keep_default_na=False` e o ponto critico: sem ele o pandas troca todo campo
    vazio por NaN -- inclusive campo vazio entre aspas, como os 2.965 de
    `order_delivered_customer_date` -- e a bronze entregaria NULL onde o
    contrato manda entregar ''. `utf-8-sig` cobre o BOM da traducao de
    categoria sem afetar os demais arquivos, que nao tem BOM.
    """
    return pd.read_csv(
        caminho,
        dtype=str,
        keep_default_na=False,
        na_filter=False,
        encoding="utf-8-sig",
    )


def adicionar_linhagem(
    dados: pd.DataFrame, fonte: FonteCSV, arquivo_origem: str, data_ingestao: datetime
) -> pd.DataFrame:
    """Acrescenta as quatro colunas da secao 3 do contrato, nessa ordem."""
    dados = dados.copy()
    dados["_fonte"] = fonte.fonte
    dados["_arquivo_origem"] = arquivo_origem
    dados["_data_ingestao"] = data_ingestao
    # Base 1 e por registro, nao por linha fisica do arquivo.
    dados["_linha_origem"] = range(1, len(dados) + 1)
    return dados


def montar_esquema(colunas_dados: list[str]) -> pa.Schema:
    """Esquema explicito: dado sempre string, linhagem com tipo proprio.

    Explicito de proposito -- deixar o pyarrow inferir abriria a porta para uma
    coluna virar int64 so porque todos os valores dela parecem numero, que e
    exatamente o que a bronze nao pode fazer.
    """
    campos = [pa.field(coluna, pa.string()) for coluna in colunas_dados]
    campos += [
        pa.field("_fonte", pa.string()),
        pa.field("_arquivo_origem", pa.string()),
        pa.field("_data_ingestao", pa.timestamp("us")),
        pa.field("_linha_origem", pa.int64()),
    ]
    return pa.schema(campos)


def gravar_parquet(dados: pd.DataFrame, colunas_dados: list[str], destino: Path) -> int:
    """Grava o parquet snappy e devolve o numero de linhas que ficou no arquivo."""
    tabela = pa.Table.from_pandas(
        dados, schema=montar_esquema(colunas_dados), preserve_index=False
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(tabela, destino, compression="snappy")
    return pq.ParquetFile(destino).metadata.num_rows


def ingerir_csv(fonte: FonteCSV, manifesto: dict, agora: datetime) -> ResultadoIngestao:
    inicio = time.perf_counter()
    caminho_origem = exigir_fonte(fonte)
    arquivo_origem = caminho_origem.name
    destino = DIR_BRONZE / f"{fonte.tabela}.parquet"

    digest = sha256_arquivo(caminho_origem)
    anterior = manifesto["fontes"].get(fonte.tabela)
    # O timestamp so anda quando a fonte muda. Exigir o parquet em disco evita
    # herdar a data de uma execucao cuja saida foi apagada.
    fonte_alterada = not (anterior and anterior["sha256"] == digest and destino.exists())
    data_ingestao = agora if fonte_alterada else datetime.fromisoformat(anterior["data_ingestao"])

    linhas_entrada = contar_registros(caminho_origem)
    dados = ler_csv_como_texto(caminho_origem)
    colunas_dados = list(dados.columns)

    if len(dados) != linhas_entrada:
        raise ContagemDivergenteError(
            f"{fonte.tabela}: o CSV tem {linhas_entrada} registros e a leitura "
            f"devolveu {len(dados)} linhas."
        )

    linhas_saida = gravar_parquet(
        adicionar_linhagem(dados, fonte, arquivo_origem, data_ingestao),
        colunas_dados,
        destino,
    )
    if linhas_saida != linhas_entrada:
        raise ContagemDivergenteError(
            f"{fonte.tabela}: origem com {linhas_entrada} linhas e parquet com "
            f"{linhas_saida}. A bronze nao pode criar nem perder linha."
        )

    manifesto["fontes"][fonte.tabela] = {
        "arquivo_origem": arquivo_origem,
        "caminho_origem": fonte.origem,
        "sha256": digest,
        "data_ingestao": data_ingestao.isoformat(),
        "linhas": linhas_saida,
    }
    gravar_manifesto(manifesto)

    return ResultadoIngestao(
        tabela=fonte.tabela,
        arquivo_origem=arquivo_origem,
        caminho_saida=destino,
        linhas_entrada=linhas_entrada,
        linhas_saida=linhas_saida,
        colunas_dados=len(colunas_dados),
        data_ingestao=data_ingestao,
        fonte_alterada=fonte_alterada,
        sha256=digest,
        duracao_s=time.perf_counter() - inicio,
    )


def executar(tabelas: list[str] | None = None) -> list[ResultadoIngestao]:
    """Roda a bronze inteira, ou so as tabelas pedidas. Ponto de entrada do pipeline."""
    selecionadas = [f for f in FONTES_CSV if tabelas is None or f.tabela in tabelas]
    if tabelas is not None:
        desconhecidas = set(tabelas) - {f.tabela for f in FONTES_CSV}
        if desconhecidas:
            raise ValueError(f"Tabela bronze desconhecida: {', '.join(sorted(desconhecidas))}")

    DIR_BRONZE.mkdir(parents=True, exist_ok=True)
    manifesto = carregar_manifesto()
    agora = datetime.now().replace(microsecond=0)

    resultados = []
    for fonte in selecionadas:
        resultado = ingerir_csv(fonte, manifesto, agora)
        resultados.append(resultado)
        logger.info(
            "%-26s %9s linhas -> %9s linhas | %2d colunas + 4 de linhagem | "
            "sha256 %s | _data_ingestao %s (%s) | %.2fs",
            resultado.tabela,
            f"{resultado.linhas_entrada:,}".replace(",", "."),
            f"{resultado.linhas_saida:,}".replace(",", "."),
            resultado.colunas_dados,
            resultado.sha256[:12],
            resultado.data_ingestao.isoformat(sep=" "),
            "fonte alterada" if resultado.fonte_alterada else "preservada",
            resultado.duracao_s,
        )
    return resultados


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    resultados = executar()
    total = sum(r.linhas_saida for r in resultados)
    logger.info("bronze concluida: %d tabelas, %s linhas", len(resultados),
                f"{total:,}".replace(",", "."))


if __name__ == "__main__":
    main()
