"""Camada bronze: ingestao fiel das fontes de `data/raw/` para Parquet.

Regra da camada, conforme a secao 3 do contrato de dados: copia literal. Toda
coluna de dado vira VARCHAR, string vazia continua string vazia, nenhuma linha
e filtrada, deduplicada ou descartada. A conversao de '' para NULL, a tipagem e
a limpeza sao da silver.

Cada tabela recebe quatro colunas de linhagem: `_fonte`, `_arquivo_origem`,
`_data_ingestao` e `_linha_origem`. As duas ultimas tem tipo proprio
(TIMESTAMP e BIGINT) porque sao metadado da ingestao, nao dado da fonte.

Sao onze tabelas: dez vindas de CSV e uma da API de localidades do IBGE, cuja
resposta fica em cache em `data/raw/ibge/municipios.json` e so e rebaixada
quando passa de trinta dias.

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
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

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


OLIST_NO_KAGGLE = "dataset 'Brazilian E-Commerce Public Dataset by Olist', no Kaggle"

# As dez fontes CSV do contrato, na ordem da tabela da secao 3.
FONTES_CSV: tuple[FonteCSV, ...] = (
    FonteCSV("olist_pedidos", "olist/olist_orders_dataset.csv", "olist", OLIST_NO_KAGGLE),
    FonteCSV("olist_itens_pedido", "olist/olist_order_items_dataset.csv", "olist", OLIST_NO_KAGGLE),
    FonteCSV("olist_produtos", "olist/olist_products_dataset.csv", "olist", OLIST_NO_KAGGLE),
    FonteCSV("olist_clientes", "olist/olist_customers_dataset.csv", "olist", OLIST_NO_KAGGLE),
    FonteCSV("olist_vendedores", "olist/olist_sellers_dataset.csv", "olist", OLIST_NO_KAGGLE),
    FonteCSV("olist_pagamentos", "olist/olist_order_payments_dataset.csv", "olist", OLIST_NO_KAGGLE),
    FonteCSV("olist_avaliacoes", "olist/olist_order_reviews_dataset.csv", "olist", OLIST_NO_KAGGLE),
    FonteCSV("olist_geolocalizacao", "olist/olist_geolocation_dataset.csv", "olist", OLIST_NO_KAGGLE),
    FonteCSV(
        "olist_traducao_categoria",
        "olist/product_category_name_translation.csv",
        "olist",
        OLIST_NO_KAGGLE,
    ),
    FonteCSV(
        "socioeconomico_municipios",
        "socioeconomico/indicadores_municipais.csv",
        "sidra",
        "consolidado das tabelas 6579 e 5938 do SIDRA por "
        "src/utils/baixar_fontes_ibge.py; ver docs/fontes_ibge_sidra.md",
    ),
)

URL_IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
CACHE_IBGE = DIR_BRUTO / "ibge" / "municipios.json"
TABELA_IBGE = "ibge_municipios"
VALIDADE_CACHE_DIAS = 30


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


class EstruturaInesperadaError(RuntimeError):
    """JSON da API veio com uma forma que a ingestao nao sabe achatar."""


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
    dados: pd.DataFrame, fonte: str, arquivo_origem: str, data_ingestao: datetime
) -> pd.DataFrame:
    """Acrescenta as quatro colunas da secao 3 do contrato, nessa ordem."""
    dados = dados.copy()
    dados["_fonte"] = fonte
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


def decidir_data_ingestao(
    tabela: str, digest: str, destino: Path, manifesto: dict, agora: datetime
) -> tuple[datetime, bool]:
    """Preserva o timestamp da execucao anterior enquanto a fonte nao mudar.

    Exigir que o parquet exista evita herdar a data de uma execucao cuja saida
    foi apagada: sem o arquivo, a ingestao e nova, mesmo com o hash igual.
    """
    anterior = manifesto["fontes"].get(tabela)
    fonte_alterada = not (anterior and anterior["sha256"] == digest and destino.exists())
    if fonte_alterada:
        return agora, True
    return datetime.fromisoformat(anterior["data_ingestao"]), False


def registrar_no_manifesto(
    manifesto: dict, tabela: str, arquivo_origem: str, caminho_origem: str,
    digest: str, data_ingestao: datetime, linhas: int,
) -> None:
    """Grava o manifesto a cada tabela, para ele sempre refletir o que esta em disco."""
    manifesto["fontes"][tabela] = {
        "arquivo_origem": arquivo_origem,
        "caminho_origem": caminho_origem,
        "sha256": digest,
        "data_ingestao": data_ingestao.isoformat(),
        "linhas": linhas,
    }
    gravar_manifesto(manifesto)


def materializar(
    dados: pd.DataFrame, colunas_dados: list[str], tabela: str, fonte: str,
    arquivo_origem: str, data_ingestao: datetime, linhas_entrada: int,
) -> tuple[Path, int]:
    """Acrescenta linhagem, grava o parquet e confere a contagem contra a origem."""
    destino = DIR_BRONZE / f"{tabela}.parquet"
    linhas_saida = gravar_parquet(
        adicionar_linhagem(dados, fonte, arquivo_origem, data_ingestao),
        colunas_dados,
        destino,
    )
    if linhas_saida != linhas_entrada:
        raise ContagemDivergenteError(
            f"{tabela}: origem com {linhas_entrada} linhas e parquet com "
            f"{linhas_saida}. A bronze nao pode criar nem perder linha."
        )
    return destino, linhas_saida


def ingerir_csv(fonte: FonteCSV, manifesto: dict, agora: datetime) -> ResultadoIngestao:
    inicio = time.perf_counter()
    caminho_origem = exigir_fonte(fonte)
    arquivo_origem = caminho_origem.name
    destino = DIR_BRONZE / f"{fonte.tabela}.parquet"

    digest = sha256_arquivo(caminho_origem)
    data_ingestao, fonte_alterada = decidir_data_ingestao(
        fonte.tabela, digest, destino, manifesto, agora
    )

    linhas_entrada = contar_registros(caminho_origem)
    dados = ler_csv_como_texto(caminho_origem)
    colunas_dados = list(dados.columns)

    if len(dados) != linhas_entrada:
        raise ContagemDivergenteError(
            f"{fonte.tabela}: o CSV tem {linhas_entrada} registros e a leitura "
            f"devolveu {len(dados)} linhas."
        )

    destino, linhas_saida = materializar(
        dados, colunas_dados, fonte.tabela, fonte.fonte, arquivo_origem,
        data_ingestao, linhas_entrada,
    )
    registrar_no_manifesto(
        manifesto, fonte.tabela, arquivo_origem, fonte.origem, digest,
        data_ingestao, linhas_saida,
    )

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


def obter_json_ibge() -> Path:
    """Devolve o JSON de municipios, reusando o cache enquanto ele valer.

    O contrato manda todos os membros trabalharem sobre o mesmo JSON, entao a
    resposta e gravada byte a byte, sem reformatar: qualquer reindentacao
    mudaria o sha256 que o grupo usa para conferir que esta comparando a
    mesma versao do cadastro.
    """
    if CACHE_IBGE.exists():
        idade = datetime.now() - datetime.fromtimestamp(CACHE_IBGE.stat().st_mtime)
        if idade < timedelta(days=VALIDADE_CACHE_DIAS):
            logger.info(
                "ibge: cache com %d dia(s) em %s; a API nao sera acessada",
                idade.days, CACHE_IBGE,
            )
            return CACHE_IBGE
        logger.info(
            "ibge: cache com %d dia(s), acima dos %d permitidos; baixando de novo",
            idade.days, VALIDADE_CACHE_DIAS,
        )
    else:
        logger.info("ibge: sem cache local; baixando de %s", URL_IBGE)

    resposta = requests.get(URL_IBGE, timeout=120)
    resposta.raise_for_status()
    CACHE_IBGE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_IBGE.write_bytes(resposta.content)
    logger.info("ibge: %s bytes gravados em %s", len(resposta.content), CACHE_IBGE)
    return CACHE_IBGE


def achatar_registro(no: dict, prefixo: str, plano: dict[str, str]) -> None:
    """Achata um municipio em pares caminho -> texto.

    O nome da coluna e o caminho no JSON com `_` no lugar do ponto e do hifen,
    em minusculas, conforme a convencao de identificadores da secao 1 do
    contrato: `microrregiao.mesorregiao.UF.sigla` vira
    `microrregiao_mesorregiao_uf_sigla`.

    Campo nulo simplesmente nao gera coluna nesse registro -- quem preenche o
    vazio e o `fillna('')` na montagem do DataFrame, que e o que mantem a
    promessa de que a bronze nao entrega NULL em coluna de dado. E o caso de
    Boa Esperanca do Norte (5101837), unico municipio sem `microrregiao`.
    """
    for chave, valor in no.items():
        caminho = f"{prefixo}_{chave}" if prefixo else chave
        caminho = caminho.replace("-", "_").lower()
        if isinstance(valor, dict):
            achatar_registro(valor, caminho, plano)
        elif isinstance(valor, list):
            # Hoje nao existe lista nenhuma na resposta. Se a API passar a
            # devolver uma, e melhor parar do que inventar uma serializacao.
            raise EstruturaInesperadaError(
                f"ibge: campo '{caminho}' veio como lista, estrutura nao prevista "
                "pela ingestao. Confira o retorno da API antes de seguir."
            )
        elif valor is not None:
            plano[caminho] = str(valor)


def ingerir_ibge(manifesto: dict, agora: datetime) -> ResultadoIngestao:
    inicio = time.perf_counter()
    caminho_origem = obter_json_ibge()
    destino = DIR_BRONZE / f"{TABELA_IBGE}.parquet"

    digest = sha256_arquivo(caminho_origem)
    # Hash exigido pelo contrato: e por ele que o grupo confere que todos estao
    # com a mesma versao do cadastro de municipios.
    logger.info("ibge: sha256 do JSON = %s", digest)
    data_ingestao, fonte_alterada = decidir_data_ingestao(
        TABELA_IBGE, digest, destino, manifesto, agora
    )

    registros = json.loads(caminho_origem.read_text(encoding="utf-8"))
    linhas_entrada = len(registros)

    colunas: dict[str, None] = {}  # dict preserva a ordem de primeira aparicao
    planos = []
    for registro in registros:
        plano: dict[str, str] = {}
        achatar_registro(registro, "", plano)
        for coluna in plano:
            colunas.setdefault(coluna)
        planos.append(plano)

    colunas_dados = list(colunas)
    dados = pd.DataFrame(planos, columns=colunas_dados).fillna("")
    incompletos = sum(1 for plano in planos if len(plano) != len(colunas_dados))
    if incompletos:
        logger.info(
            "ibge: %d municipio(s) sem algum ramo da hierarquia; colunas ausentes gravadas como ''",
            incompletos,
        )

    destino, linhas_saida = materializar(
        dados, colunas_dados, TABELA_IBGE, "ibge_api", URL_IBGE,
        data_ingestao, linhas_entrada,
    )
    registrar_no_manifesto(
        manifesto, TABELA_IBGE, URL_IBGE,
        CACHE_IBGE.relative_to(DIR_BRUTO).as_posix(), digest, data_ingestao, linhas_saida,
    )

    return ResultadoIngestao(
        tabela=TABELA_IBGE,
        arquivo_origem=URL_IBGE,
        caminho_saida=destino,
        linhas_entrada=linhas_entrada,
        linhas_saida=linhas_saida,
        colunas_dados=len(colunas_dados),
        data_ingestao=data_ingestao,
        fonte_alterada=fonte_alterada,
        sha256=digest,
        duracao_s=time.perf_counter() - inicio,
    )


def tabelas_disponiveis() -> list[str]:
    """As onze tabelas da secao 3 do contrato, na ordem em que sao ingeridas."""
    return [f.tabela for f in FONTES_CSV] + [TABELA_IBGE]


def executar(tabelas: list[str] | None = None) -> list[ResultadoIngestao]:
    """Roda a bronze inteira, ou so as tabelas pedidas. Ponto de entrada do pipeline."""
    if tabelas is not None:
        desconhecidas = set(tabelas) - set(tabelas_disponiveis())
        if desconhecidas:
            raise ValueError(f"Tabela bronze desconhecida: {', '.join(sorted(desconhecidas))}")

    DIR_BRONZE.mkdir(parents=True, exist_ok=True)
    manifesto = carregar_manifesto()
    agora = datetime.now().replace(microsecond=0)

    trabalho = [(f.tabela, lambda f=f: ingerir_csv(f, manifesto, agora)) for f in FONTES_CSV]
    trabalho.append((TABELA_IBGE, lambda: ingerir_ibge(manifesto, agora)))

    resultados = []
    for tabela, ingerir in trabalho:
        if tabelas is not None and tabela not in tabelas:
            continue
        resultado = ingerir()
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
