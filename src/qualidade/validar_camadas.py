"""Validacao das camadas bronze e silver.

`docs/plano_qualidade.md` define as verificacoes da gold (`GOLD-PK-*`,
`GOLD-FK-*` ...), que rodam depois da modelagem dimensional. Para a bronze e a
silver ele so pede contagem de linha (secoes 5.1 e 5.2). Este modulo cobre o
vao: executa sobre as duas camadas as mesmas classes de verificacao que o plano
exige da gold -- unicidade, grao, integridade referencial, reconciliacao
monetaria e regra de negocio -- e grava o resultado com os valores reais.

Nao reimplementa nada: importa as constantes dos modulos que valida
(`BRONZE_ESPERADA`, a caixa delimitadora do Brasil, `RAIO_ACEITE_KM`,
`contar_registros`, `sha256_arquivo`). Se a regra mudar na camada, a validacao
acompanha em vez de divergir em silencio.

Familias de teste:

    BRZ-*   bronze: copia literal, linhagem, contagem contra a origem
    SLV-*   silver: PK, orfao, grao preservado, reconciliacao, regra de negocio
    INT-*   integracao municipal: metodo de match, raio, unicidade do mapeamento
    CTR-*   conformidade com docs/contratos_dados.md (so reporta, nao corrige)
    REP-*   reprodutibilidade: etapa ausente, artefato orfao, de-para

Classificacao e desfecho seguem `docs/plano_qualidade.md` secoes 3 e 20:
REPROVADO derruba a execucao, mas so depois do relatorio estar gravado.

Saidas:

    docs/validacao_bronze_silver.md               relatorio legivel
    data/silver/validacao_bronze_silver.json      mesmos dados para a gold

Execucao:

    .venv\\Scripts\\python.exe -m src.qualidade.validar_camadas
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import duckdb

from ..bronze import ingest
from ..silver import transform

RAIZ = Path(__file__).resolve().parents[2]
DIR_BRONZE = RAIZ / "data" / "bronze"
DIR_SILVER = RAIZ / "data" / "silver"
DIR_DOCS = RAIZ / "docs"

RELATORIO_MD = DIR_DOCS / "validacao_bronze_silver.md"
RELATORIO_JSON = DIR_SILVER / "validacao_bronze_silver.json"

APROVADO = "APROVADO"
REPROVADO = "REPROVADO"
ALERTA = "ALERTA"
NAO_EXECUTADO = "NAO EXECUTADO"

log = logging.getLogger("validar_camadas")


# --------------------------------------------------------------------------
# Inventario das camadas
# --------------------------------------------------------------------------

# Grao de cada tabela da silver, conforme docs/silver_contrato.md secao 2 e
# docs/contratos_dados.md secao 5.3. `None` = tabela sem PK declarada.
GRAO_SILVER: dict[str, tuple[str, ...] | None] = {
    "pedidos": ("order_id",),
    "itens_pedido": ("order_id", "item_pedido_id"),
    "pagamentos": ("order_id",),
    "avaliacoes": ("order_id",),
    "produtos": ("product_id",),
    "clientes": ("customer_id",),
    "vendedores": ("seller_id",),
    "geolocalizacao_pontos": None,
    "geolocalizacao_cep": ("cep_prefixo",),
    "municipios": ("cod_ibge",),
}

# Saidas da etapa de integracao municipal (membro 3). Ausentes quando a etapa
# ainda nao rodou -- os testes INT-* saem como NAO EXECUTADO, nao como falha.
GRAO_INTEGRACAO: dict[str, tuple[str, ...]] = {
    "municipios_cliente": ("customer_id",),
    "municipios_vendedor": ("seller_id",),
    "clientes_municipios": ("customer_id",),
    "vendedores_municipios": ("seller_id",),
    "geografia_integrada": ("cod_ibge",),
    "distancias_itens": ("order_id", "order_item_id"),
    "distancias_vendedor_cliente": ("seller_id", "customer_id"),
}

# Colunas sem as quais os testes de valor nao tem o que medir. Conferidas
# antes deles: coluna ausente e das falhas que interrompem o pipeline (plano
# de qualidade secao 3.1), e precisa sair como REPROVADO no relatorio, nao
# como erro de binder no meio da execucao.
COLUNAS_OBRIGATORIAS: dict[str, tuple[str, ...]] = {
    "pedidos": (
        "order_id", "customer_id", "status_pedido", "ts_compra", "ts_aprovacao",
        "ts_envio_transportadora", "ts_entrega_cliente", "ts_estimativa_entrega",
        "flag_entrega_ausente", "dias_ate_entrega", "dias_atraso", "flag_atraso",
    ),
    "itens_pedido": (
        "order_id", "item_pedido_id", "product_id", "seller_id", "preco_produto",
        "valor_frete", "valor_total_item", "faixa_preco", "flag_frete_outlier",
    ),
    "pagamentos": (
        "order_id", "valor_total_pago", "tipo_pagamento_predominante",
        "parcelas_tipo_predominante", "qtd_metodos_distintos",
    ),
    "avaliacoes": ("order_id", "review_id", "nota_review"),
    "produtos": (
        "product_id", "categoria_produto", "categoria_produto_ingles", "peso_g",
        "comprimento_cm", "altura_cm", "largura_cm", "flag_peso_imputado",
        "flag_dimensoes_imputadas",
    ),
    "clientes": ("customer_id", "customer_unique_id", "cep_prefixo", "cidade", "uf"),
    "vendedores": ("seller_id", "cep_prefixo", "cidade", "uf"),
    "geolocalizacao_pontos": (
        "cep_prefixo", "latitude", "longitude", "flag_coordenada_invalida",
    ),
    "geolocalizacao_cep": (
        "cep_prefixo", "latitude_mediana", "longitude_mediana", "qtd_pontos_validos",
    ),
    "municipios": (
        "cod_ibge", "municipio", "municipio_normalizado", "uf", "populacao",
        "pib_per_capita", "porte_municipio",
    ),
}

# Chaves estrangeiras internas da silver. A silver nao junta entidades, mas as
# referencias precisam fechar antes de a gold montar as fatos.
FK_SILVER: tuple[tuple[str, str, str, str], ...] = (
    ("itens_pedido", "order_id", "pedidos", "order_id"),
    ("itens_pedido", "product_id", "produtos", "product_id"),
    ("itens_pedido", "seller_id", "vendedores", "seller_id"),
    ("pedidos", "customer_id", "clientes", "customer_id"),
    ("pagamentos", "order_id", "pedidos", "order_id"),
    ("avaliacoes", "order_id", "pedidos", "order_id"),
)

# Grao preservado da bronze para a silver. `True` = a silver tem de ter
# exatamente as linhas da bronze; `False` = a silver agrega por order_id, e a
# comparacao correta e contra o count(distinct order_id) da bronze.
GRAO_PRESERVADO: tuple[tuple[str, str, bool], ...] = (
    ("pedidos", "olist_pedidos", True),
    ("itens_pedido", "olist_itens_pedido", True),
    ("produtos", "olist_produtos", True),
    ("clientes", "olist_clientes", True),
    ("vendedores", "olist_vendedores", True),
    ("geolocalizacao_pontos", "olist_geolocalizacao", True),
    ("municipios", "ibge_municipios", True),
    ("pagamentos", "olist_pagamentos", False),
    ("avaliacoes", "olist_avaliacoes", False),
)


# --------------------------------------------------------------------------
# Contrato de dados -- esperado por docs/contratos_dados.md secao 4
# --------------------------------------------------------------------------

# Nome de arquivo fixado no contrato -> nome que a silver realmente grava.
CONTRATO_ARQUIVOS: dict[str, str] = {
    "pagamentos_pedido.parquet": "pagamentos.parquet",
    "avaliacoes_pedido.parquet": "avaliacoes.parquet",
    "geolocalizacao_agregada.parquet": "geolocalizacao_cep.parquet",
}

# Coluna do contrato -> coluna equivalente na silver, ou None quando a silver
# nao produz nada equivalente. Secoes 4.1 a 4.9.
CONTRATO_COLUNAS: dict[str, tuple[str, dict[str, str | None]]] = {
    "4.1 pedidos": (
        "pedidos",
        {
            "data_compra": "ts_compra",
            "data_aprovacao": "ts_aprovacao",
            "data_envio_transportadora": "ts_envio_transportadora",
            "data_entrega_cliente": "ts_entrega_cliente",
            "data_entrega_estimada": "ts_estimativa_entrega",
            "flag_entregue": None,
        },
    ),
    "4.2 itens_pedido": (
        "itens_pedido",
        {
            "order_item_id": "item_pedido_id",
            "data_limite_envio": "ts_limite_envio",
            "valor_produto": "preco_produto",
        },
    ),
    "4.3 produtos": (
        "produtos",
        {
            "categoria_pt": "categoria_produto",
            "categoria_en": "categoria_produto_ingles",
            "volume_cm3": None,
            "qtd_fotos": None,
            "flag_imputado": None,
        },
    ),
    "4.4 clientes": (
        "clientes",
        {"cidade_origem": "cidade", "uf_origem": "uf"},
    ),
    "4.5 vendedores": (
        "vendedores",
        {"cidade_origem": "cidade", "uf_origem": "uf"},
    ),
    "4.6 pagamentos_pedido": (
        "pagamentos",
        {
            "qtd_parcelas": "parcelas_tipo_predominante",
            "valor_pago_total": "valor_total_pago",
            "qtd_meios_pagamento": "qtd_metodos_distintos",
        },
    ),
    "4.7 avaliacoes_pedido": (
        "avaliacoes",
        {
            "nota_avaliacao": "nota_review",
            "data_avaliacao": "ts_criacao_review",
            "flag_tem_comentario": None,
        },
    ),
    "4.8 geolocalizacao_agregada": (
        "geolocalizacao_cep",
        {
            "latitude": "latitude_mediana",
            "longitude": "longitude_mediana",
            "qtd_pontos": "qtd_pontos_validos",
        },
    ),
}

# Tipo fixado pelo contrato -> tipo que a silver gravou. Secao 1 (monetario
# sempre DECIMAL(12,2), distancia DECIMAL(10,2)) e secoes 4.3 e 4.8.
CONTRATO_TIPOS: tuple[tuple[str, str, str, str], ...] = (
    ("itens_pedido", "valor_total_item", "DECIMAL(12,2)", "4.2"),
    ("pagamentos", "valor_total_pago", "DECIMAL(12,2)", "4.6"),
    ("produtos", "peso_g", "DECIMAL(10,2)", "4.3"),
    ("produtos", "comprimento_cm", "DECIMAL(10,2)", "4.3"),
    ("geolocalizacao_cep", "latitude_mediana", "DECIMAL(9,6)", "4.8"),
    ("geolocalizacao_cep", "longitude_mediana", "DECIMAL(9,6)", "4.8"),
)

# Regras onde a implementacao e o contrato divergem no metodo, nao no nome.
CONTRATO_REGRAS: tuple[tuple[str, str, str, str], ...] = (
    (
        "CTR-REGRA-001",
        "Regra do outlier de frete",
        "contrato 4.2: valor_frete acima do p99",
        "implementado: cerca de Tukey, Q3 + 1.5 * IQR (silver_contrato 4)",
    ),
    (
        "CTR-REGRA-002",
        "Desempate do tipo de pagamento predominante",
        "contrato 4.6: ordem fixa credit_card > boleto > debit_card > voucher",
        "implementado: ordem alfabetica ascendente de payment_type",
    ),
    (
        "CTR-REGRA-003",
        "Texto do comentario da avaliacao",
        "contrato 4.7: o texto do comentario nao e carregado",
        "implementado: titulo_review e mensagem_review carregados na silver",
    ),
)

VOCABULARIO_MATCH = ("exato", "geografico", "de_para", "nao_resolvido")


# --------------------------------------------------------------------------
# Resultado de um teste
# --------------------------------------------------------------------------


@dataclass
class Resultado:
    """Um teste executado, na estrutura de docs/plano_qualidade.md secao 4."""

    id: str
    categoria: str
    descricao: str
    esperado: str
    encontrado: str
    status: str
    detalhes: str = ""

    def como_dict(self) -> dict:
        return {
            "id": self.id,
            "categoria": self.categoria,
            "descricao": self.descricao,
            "esperado": self.esperado,
            "encontrado": self.encontrado,
            "status": self.status,
            "detalhes": self.detalhes,
        }


@dataclass
class Validador:
    """Acumula resultados sobre uma conexao DuckDB somente de leitura."""

    con: duckdb.DuckDBPyConnection
    resultados: list[Resultado] = field(default_factory=list)
    contagens: dict[str, dict[str, int]] = field(default_factory=dict)
    disponivel: set[str] = field(default_factory=set)

    # -- helpers ----------------------------------------------------------

    def contar(self, sql: str) -> int:
        return int(self.con.execute(sql).fetchone()[0])

    def medir(self, sql: str) -> object | None:
        """Primeiro valor da consulta, ou None se ela nao puder ser executada.

        Usado onde o teste informa um valor em vez de contar ocorrencias: sem
        isso uma coluna ausente derrubaria a execucao antes do relatorio.
        """
        try:
            return self.con.execute(sql).fetchone()[0]
        except duckdb.Error:
            return None

    def registrar(
        self,
        id_: str,
        categoria: str,
        descricao: str,
        esperado: object,
        encontrado: object,
        status: str,
        detalhes: str = "",
    ) -> Resultado:
        resultado = Resultado(
            id_, categoria, descricao, str(esperado), str(encontrado), status, detalhes
        )
        self.resultados.append(resultado)
        return resultado

    def zero(
        self,
        id_: str,
        categoria: str,
        descricao: str,
        sql: str,
        status_falha: str = REPROVADO,
        detalhes: str = "",
    ) -> Resultado:
        """Teste cujo criterio de aceite e nenhuma ocorrencia.

        Um teste que nao consegue rodar (coluna sumiu, tipo mudou) reprova em
        vez de derrubar a execucao com o erro do DuckDB: o relatorio precisa
        chegar gravado ate quando a camada esta quebrada demais para medir.
        """
        try:
            n = self.contar(sql)
        except duckdb.Error as erro:
            return self.registrar(
                id_, categoria, descricao, 0, "nao mensuravel", REPROVADO,
                f"{detalhes} | consulta falhou: {erro}".lstrip(" |"),
            )
        return self.registrar(
            id_, categoria, descricao, 0, n, APROVADO if n == 0 else status_falha, detalhes
        )

    def igual(
        self,
        id_: str,
        categoria: str,
        descricao: str,
        esperado: object,
        encontrado: object,
        status_falha: str = REPROVADO,
        detalhes: str = "",
    ) -> Resultado:
        status = APROVADO if esperado == encontrado else status_falha
        return self.registrar(
            id_, categoria, descricao, esperado, encontrado, status, detalhes
        )

    def pular(self, id_: str, categoria: str, descricao: str, motivo: str) -> Resultado:
        return self.registrar(id_, categoria, descricao, "-", "-", NAO_EXECUTADO, motivo)


# --------------------------------------------------------------------------
# Preparacao: registra as tabelas existentes como view
# --------------------------------------------------------------------------


def _modulo_integracao():
    """Modulo da etapa de integracao municipal, ou None se ainda nao existe.

    A etapa e de outro membro e pode nao estar escrita. A validacao precisa
    rodar mesmo assim -- e justamente a ausencia dela com saida em disco que o
    teste REP-001 procura.
    """
    try:
        from ..silver import integracao_municipios
    except ImportError:
        return None
    return integracao_municipios


def _colunas(con: duckdb.DuckDBPyConnection, view: str) -> dict[str, str]:
    return {
        linha[0]: linha[1]
        for linha in con.execute(f"describe select * from {view}").fetchall()
    }


def preparar(val: Validador) -> None:
    """Registra uma view por parquet presente em data/bronze e data/silver.

    Trabalhar com view em vez de `read_parquet` repetido deixa o SQL dos testes
    legivel e garante que todos leiam exatamente o mesmo arquivo.
    """
    for caminho in sorted(DIR_BRONZE.glob("*.parquet")):
        view = f"brz_{caminho.stem}"
        val.con.execute(
            f"create or replace view {view} as "
            f"select * from read_parquet('{caminho.as_posix()}')"
        )
        val.disponivel.add(view)

    for caminho in sorted(DIR_SILVER.glob("*.parquet")):
        view = f"slv_{caminho.stem}"
        val.con.execute(
            f"create or replace view {view} as "
            f"select * from read_parquet('{caminho.as_posix()}')"
        )
        val.disponivel.add(view)


def _inventariar(val: Validador) -> None:
    for camada, prefixo in (("bronze", "brz_"), ("silver", "slv_")):
        linhas = {
            view[len(prefixo) :]: val.contar(f"select count(*) from {view}")
            for view in sorted(val.disponivel)
            if view.startswith(prefixo)
        }
        val.contagens[camada] = linhas


# --------------------------------------------------------------------------
# BRZ-* -- bronze
# --------------------------------------------------------------------------

LINHAGEM_ESPERADA = {
    "_fonte": "VARCHAR",
    "_arquivo_origem": "VARCHAR",
    "_data_ingestao": "TIMESTAMP",
    "_linha_origem": "BIGINT",
}


def validar_bronze(val: Validador) -> None:
    """A bronze promete copia literal; os testes medem exatamente isso."""
    manifesto = ingest.carregar_manifesto().get("fontes", {})
    esperadas = ingest.tabelas_disponiveis()

    ausentes = [t for t in esperadas if f"brz_{t}" not in val.disponivel]
    val.igual(
        "BRZ-EST-001",
        "Estrutura",
        "Tabelas da bronze presentes em data/bronze/",
        len(esperadas),
        len(esperadas) - len(ausentes),
        detalhes=("ausente(s): " + ", ".join(ausentes)) if ausentes else "",
    )

    if ausentes:
        val.pular(
            "BRZ-EST-002",
            "Estrutura",
            "Demais verificacoes da bronze",
            "tabela obrigatoria ausente; rode python -m src.run_pipeline --etapa bronze",
        )
        return

    sem_linhagem: list[str] = []
    tipo_errado: list[str] = []
    nao_varchar: list[str] = []
    com_nulo: list[str] = []
    linha_origem_quebrada: list[str] = []
    fonte_invalida: list[str] = []

    for tabela in esperadas:
        view = f"brz_{tabela}"
        colunas = _colunas(val.con, view)

        for coluna, tipo in LINHAGEM_ESPERADA.items():
            if coluna not in colunas:
                sem_linhagem.append(f"{tabela}.{coluna}")
            elif not colunas[coluna].startswith(tipo):
                tipo_errado.append(f"{tabela}.{coluna}={colunas[coluna]}")

        dados = [c for c in colunas if not c.startswith("_")]
        nao_varchar += [
            f"{tabela}.{c}={colunas[c]}" for c in dados if colunas[c] != "VARCHAR"
        ]

        # A bronze preserva '' tal como esta e nunca converte para NULL
        # (contrato secao 2). Um NULL aqui significa que a leitura converteu.
        if dados:
            condicao = " or ".join(f'"{c}" is null' for c in dados)
            n = val.contar(f"select count(*) from {view} where {condicao}")
            if n:
                com_nulo.append(f"{tabela}: {n}")

        total = val.contar(f"select count(*) from {view}")
        sequencia = val.contar(
            f"select count(*) from {view} "
            f"where _linha_origem is null or _linha_origem < 1 or _linha_origem > {total}"
        )
        distintos = val.contar(f"select count(distinct _linha_origem) from {view}")
        if sequencia or distintos != total:
            linha_origem_quebrada.append(
                f"{tabela}: {sequencia} fora da faixa, {distintos} distintos de {total}"
            )

        n = val.contar(
            f"select count(*) from {view} "
            "where _fonte not in ('olist', 'sidra', 'ibge_api')"
        )
        if n:
            fonte_invalida.append(f"{tabela}: {n}")

    val.igual(
        "BRZ-EST-002",
        "Estrutura",
        "Colunas de linhagem presentes em todas as tabelas",
        0,
        len(sem_linhagem),
        detalhes="; ".join(sem_linhagem),
    )
    val.igual(
        "BRZ-EST-003",
        "Estrutura",
        "Colunas de linhagem com o tipo do contrato secao 3",
        0,
        len(tipo_errado),
        detalhes="; ".join(tipo_errado),
    )
    val.igual(
        "BRZ-EST-004",
        "Estrutura",
        "Toda coluna de dado e VARCHAR (contrato secao 3)",
        0,
        len(nao_varchar),
        detalhes="; ".join(nao_varchar),
    )
    val.igual(
        "BRZ-EST-005",
        "Nulos",
        "Nenhum NULL em coluna de dado: a bronze preserva '' (contrato secao 2)",
        0,
        len(com_nulo),
        detalhes="; ".join(com_nulo),
    )
    val.igual(
        "BRZ-LIN-001",
        "Linhagem",
        "_linha_origem cobre 1..N sem buraco nem repeticao",
        0,
        len(linha_origem_quebrada),
        detalhes="; ".join(linha_origem_quebrada),
    )
    val.igual(
        "BRZ-LIN-002",
        "Linhagem",
        "_fonte dentro de olist / sidra / ibge_api",
        0,
        len(fonte_invalida),
        detalhes="; ".join(fonte_invalida),
    )

    _validar_bronze_contra_origem(val, manifesto, esperadas)


def _contar_origem(tabela: str) -> tuple[int | None, Path | None]:
    """Reconta a origem em data/raw/ pelo mesmo caminho que a ingestao usa."""
    if tabela == ingest.TABELA_IBGE:
        if not ingest.CACHE_IBGE.exists():
            return None, None
        registros = json.loads(ingest.CACHE_IBGE.read_text(encoding="utf-8"))
        return len(registros), ingest.CACHE_IBGE

    for fonte in ingest.FONTES_CSV:
        if fonte.tabela == tabela:
            caminho = ingest.DIR_BRUTO / fonte.origem
            if not caminho.exists():
                return None, None
            return ingest.contar_registros(caminho), caminho
    return None, None


def _validar_bronze_contra_origem(
    val: Validador, manifesto: dict, esperadas: list[str]
) -> None:
    """Reconta e re-hasheia data/raw/ -- e o que pega parquet desatualizado.

    O manifesto sozinho nao serve de prova: ele registra o que a ingestao
    achou na epoca. Recontar a origem agora e conferir o sha256 pega tanto o
    parquet velho quanto a fonte trocada sem reingestao.
    """
    divergencia_manifesto: list[str] = []
    divergencia_origem: list[str] = []
    divergencia_hash: list[str] = []
    sem_origem: list[str] = []

    for tabela in esperadas:
        linhas = val.contar(f"select count(*) from brz_{tabela}")
        registro = manifesto.get(tabela)

        if registro is None:
            divergencia_manifesto.append(f"{tabela}: sem entrada no manifesto")
        elif registro.get("linhas") != linhas:
            divergencia_manifesto.append(
                f"{tabela}: parquet {linhas}, manifesto {registro.get('linhas')}"
            )

        origem_linhas, caminho = _contar_origem(tabela)
        if origem_linhas is None or caminho is None:
            sem_origem.append(tabela)
            continue

        if origem_linhas != linhas:
            divergencia_origem.append(
                f"{tabela}: origem {origem_linhas}, parquet {linhas}"
            )

        if registro and registro.get("sha256") != ingest.sha256_arquivo(caminho):
            divergencia_hash.append(tabela)

    val.igual(
        "BRZ-CNT-001",
        "Contagem",
        "Linhas do parquet iguais as do _manifesto.json",
        0,
        len(divergencia_manifesto),
        detalhes="; ".join(divergencia_manifesto),
    )
    val.igual(
        "BRZ-CNT-002",
        "Contagem",
        "Linhas do parquet iguais a recontagem da origem em data/raw/",
        0,
        len(divergencia_origem),
        detalhes="; ".join(divergencia_origem),
    )
    val.igual(
        "BRZ-CNT-003",
        "Integridade da fonte",
        "sha256 da origem igual ao registrado no manifesto",
        0,
        len(divergencia_hash),
        detalhes=(
            "fonte alterada sem reingestao: " + ", ".join(divergencia_hash)
        )
        if divergencia_hash
        else "",
    )
    if sem_origem:
        val.registrar(
            "BRZ-CNT-004",
            "Contagem",
            "Origens disponiveis em data/raw/ para recontagem",
            "todas",
            f"{len(sem_origem)} ausente(s)",
            ALERTA,
            "sem recontagem independente: " + ", ".join(sem_origem),
        )


# --------------------------------------------------------------------------
# SLV-* -- silver
# --------------------------------------------------------------------------


def validar_silver(val: Validador) -> None:
    ausentes = [t for t in GRAO_SILVER if f"slv_{t}" not in val.disponivel]
    val.igual(
        "SLV-EST-001",
        "Estrutura",
        "Tabelas da silver presentes em data/silver/",
        len(GRAO_SILVER),
        len(GRAO_SILVER) - len(ausentes),
        detalhes=("ausente(s): " + ", ".join(ausentes)) if ausentes else "",
    )
    if ausentes:
        val.pular(
            "SLV-PK-001",
            "Unicidade",
            "Demais verificacoes da silver",
            "tabela obrigatoria ausente; rode python -m src.run_pipeline --etapa silver",
        )
        return

    faltando_coluna: list[str] = []
    for tabela, obrigatorias in COLUNAS_OBRIGATORIAS.items():
        view = f"slv_{tabela}"
        if view not in val.disponivel:
            continue
        presentes = _colunas(val.con, view)
        faltando_coluna += [
            f"{tabela}.{c}" for c in obrigatorias if c not in presentes
        ]
    val.igual(
        "SLV-EST-002",
        "Estrutura",
        "Colunas obrigatorias presentes em cada tabela da silver",
        0,
        len(faltando_coluna),
        detalhes="; ".join(faltando_coluna),
    )

    _validar_chaves(val, "SLV-PK", GRAO_SILVER, "slv_")
    _validar_fk_silver(val)
    _validar_grao_preservado(val)
    _validar_reconciliacao(val)
    _validar_regras_pedidos(val)
    _validar_dominios(val)
    _validar_produtos(val)
    _validar_geolocalizacao(val)


def _validar_chaves(
    val: Validador,
    prefixo_id: str,
    graos: dict[str, tuple[str, ...] | None],
    prefixo_view: str,
) -> None:
    for indice, (tabela, grao) in enumerate(graos.items(), start=1):
        view = f"{prefixo_view}{tabela}"
        if view not in val.disponivel:
            continue
        if grao is None:
            continue
        chave = ", ".join(grao)
        nulos = " or ".join(f"{c} is null" for c in grao)
        val.zero(
            f"{prefixo_id}-{indice:03d}",
            "Unicidade",
            f"{tabela}: 1 linha por ({chave})",
            f"select count(*) from (select {chave} from {view} "
            f"group by {chave} having count(*) > 1)",
        )
        val.zero(
            f"{prefixo_id}-NUL-{indice:03d}",
            "Unicidade",
            f"{tabela}: chave ({chave}) nao nula",
            f"select count(*) from {view} where {nulos}",
        )


def _validar_fk_silver(val: Validador) -> None:
    for indice, (ft, fc, dt, dc) in enumerate(FK_SILVER, start=1):
        val.zero(
            f"SLV-FK-{indice:03d}",
            "Integridade referencial",
            f"{ft}.{fc} sem correspondente em {dt}.{dc}",
            f"select count(*) from slv_{ft} f "
            f"left join slv_{dt} d on f.{fc} = d.{dc} "
            f"where f.{fc} is not null and d.{dc} is null",
        )


def _validar_grao_preservado(val: Validador) -> None:
    """Contrato secao 4.2: nenhuma linha pode ser criada ou perdida.

    O `transform.py` nao confere isso depois de gravar; aqui a contagem da
    silver e comparada com a da bronze, e a divergencia reprova.
    """
    for indice, (tabela, bronze, linha_a_linha) in enumerate(GRAO_PRESERVADO, start=1):
        view_brz, view_slv = f"brz_{bronze}", f"slv_{tabela}"
        if view_brz not in val.disponivel or view_slv not in val.disponivel:
            continue
        if linha_a_linha:
            esperado = val.contar(f"select count(*) from {view_brz}")
            descricao = f"{tabela}: mesma contagem de {bronze}"
        else:
            esperado = val.contar(f"select count(distinct order_id) from {view_brz}")
            descricao = f"{tabela}: 1 linha por order_id distinto de {bronze}"
        encontrado = val.contar(f"select count(*) from {view_slv}")
        val.igual(
            f"SLV-GRAO-{indice:03d}",
            "Preservacao de grao",
            descricao,
            esperado,
            encontrado,
        )


def _validar_reconciliacao(val: Validador) -> None:
    """Valores monetarios comparados em DECIMAL, sem tolerancia (plano 10.2)."""
    medidas = (
        ("SLV-REC-001", "valor dos produtos", "price", "preco_produto", "slv_itens_pedido", "brz_olist_itens_pedido"),
        ("SLV-REC-002", "valor do frete", "freight_value", "valor_frete", "slv_itens_pedido", "brz_olist_itens_pedido"),
        ("SLV-REC-003", "valor pago", "payment_value", "valor_total_pago", "slv_pagamentos", "brz_olist_pagamentos"),
    )
    for id_, rotulo, coluna_brz, coluna_slv, view_slv, view_brz in medidas:
        bronze = val.medir(
            f"select coalesce(sum(cast(nullif(trim({coluna_brz}), '') "
            f"as decimal(18, 2))), 0) from {view_brz}"
        )
        silver = val.medir(f"select coalesce(sum({coluna_slv}), 0) from {view_slv}")
        val.igual(
            id_,
            "Reconciliacao monetaria",
            f"Soma do {rotulo}: bronze x silver",
            f"{bronze:.2f}" if bronze is not None else "nao mensuravel",
            f"{silver:.2f}" if silver is not None else "nao mensuravel",
            detalhes="comparacao em DECIMAL, sem tolerancia de ponto flutuante",
        )

    val.zero(
        "SLV-REC-004",
        "Reconciliacao monetaria",
        "valor_total_item diferente de preco_produto + valor_frete",
        "select count(*) from slv_itens_pedido "
        "where valor_total_item is distinct from preco_produto + valor_frete",
    )


def _validar_regras_pedidos(val: Validador) -> None:
    """Regras de docs/silver_contrato.md secao 3 e plano_qualidade secao 11."""
    regras = (
        (
            "SLV-NEG-001",
            "ts_compra nunca nulo (contrato 4.1)",
            "select count(*) from slv_pedidos where ts_compra is null",
            REPROVADO,
        ),
        (
            "SLV-NEG-002",
            "ts_estimativa_entrega nunca nulo (contrato 4.1)",
            "select count(*) from slv_pedidos where ts_estimativa_entrega is null",
            REPROVADO,
        ),
        (
            "SLV-NEG-003",
            "Pedido nao entregue sem metrica de prazo preenchida",
            "select count(*) from slv_pedidos where status_pedido <> 'delivered' "
            "and (dias_ate_entrega is not null or dias_atraso is not null "
            "or flag_atraso is not null)",
            REPROVADO,
        ),
        (
            "SLV-NEG-004",
            "flag_atraso coerente com o sinal de dias_atraso",
            "select count(*) from slv_pedidos where "
            "(flag_atraso and dias_atraso <= 0) or (not flag_atraso and dias_atraso > 0)",
            REPROVADO,
        ),
        (
            "SLV-NEG-005",
            "dias_ate_entrega nunca negativo",
            "select count(*) from slv_pedidos where dias_ate_entrega < 0",
            REPROVADO,
        ),
    )
    for id_, descricao, sql, status in regras:
        val.zero(id_, "Regra de negocio", descricao, sql, status)

    # Inconsistencia conhecida do dataset Olist, preservada de proposito
    # (docs/silver_contrato.md secao 3): alerta, nunca correcao silenciosa.
    n = val.contar(
        "select count(*) from slv_pedidos "
        "where status_pedido = 'delivered' and ts_entrega_cliente is null"
    )
    val.registrar(
        "SLV-NEG-006",
        "Regra de negocio",
        "Pedidos 'delivered' sem data real de entrega",
        "documentado como alerta (plano 11.3)",
        n,
        APROVADO if n == 0 else ALERTA,
        "inconsistencia da origem, preservada e sinalizada por flag_entrega_ausente",
    )
    # A flag marca a anomalia, nao a data nula: pedido cancelado sem entrega e
    # nulo legitimo (contrato secao 2), e nao deve ser sinalizado.
    val.zero(
        "SLV-NEG-007",
        "Regra de negocio",
        "flag_entrega_ausente marca so 'delivered' sem data real de entrega",
        "select count(*) from slv_pedidos where flag_entrega_ausente is distinct from "
        "(status_pedido = 'delivered' and ts_entrega_cliente is null)",
    )


def _validar_dominios(val: Validador) -> None:
    val.zero(
        "SLV-DOM-001",
        "Dominio",
        "nota_review entre 1 e 5, sem nulo (contrato 4.7)",
        "select count(*) from slv_avaliacoes "
        "where nota_review is null or nota_review not between 1 and 5",
    )
    val.zero(
        "SLV-DOM-002",
        "Dominio",
        "faixa_preco dentro das quatro faixas do silver_contrato 4",
        "select count(*) from slv_itens_pedido where faixa_preco not in "
        "('baixo', 'medio_baixo', 'medio_alto', 'alto')",
    )
    for indice, (tabela, coluna) in enumerate(
        (
            ("clientes", "cep_prefixo"),
            ("vendedores", "cep_prefixo"),
            ("geolocalizacao_cep", "cep_prefixo"),
        ),
        start=3,
    ):
        val.zero(
            f"SLV-DOM-{indice:03d}",
            "Dominio",
            f"{tabela}.{coluna} com 5 digitos e zero a esquerda preservado",
            f"select count(*) from slv_{tabela} "
            f"where {coluna} is null or not regexp_matches({coluna}, '^[0-9]{{5}}$')",
        )
    val.zero(
        "SLV-DOM-006",
        "Dominio",
        "porte_municipio dentro das faixas do contrato 4.9",
        "select count(*) from slv_municipios where porte_municipio not in "
        "('Pequeno', 'Médio', 'Grande', 'Não informado')",
    )


def _validar_produtos(val: Validador) -> None:
    val.zero(
        "SLV-PRD-001",
        "Imputacao",
        "Produto sem categoria recebe 'nao_informado', nunca nulo (contrato 4.3)",
        "select count(*) from slv_produtos where categoria_produto is null",
    )
    # A flag tem de refletir alteracao real (plano 16): marcada sem valor
    # preenchido seria imputacao fantasma.
    val.zero(
        "SLV-PRD-002",
        "Imputacao",
        "flag_peso_imputado nunca marcada com peso_g nulo",
        "select count(*) from slv_produtos where flag_peso_imputado and peso_g is null",
    )
    val.zero(
        "SLV-PRD-003",
        "Imputacao",
        "flag_dimensoes_imputadas nunca marcada com dimensao nula",
        "select count(*) from slv_produtos where flag_dimensoes_imputadas "
        "and (comprimento_cm is null or altura_cm is null or largura_cm is null)",
    )

    sem_categoria = val.medir(
        "select count(*) from slv_produtos where categoria_produto = 'nao_informado'"
    )
    val.registrar(
        "SLV-PRD-004",
        "Imputacao",
        "Produtos com categoria 'nao_informado'",
        "documentado (plano 16)",
        sem_categoria if sem_categoria is not None else "nao mensuravel",
        APROVADO if sem_categoria == 0 else ALERTA,
        "produto sem categoria nao pode ser descartado",
    )
    sem_peso = val.medir("select count(*) from slv_produtos where peso_g is null")
    val.registrar(
        "SLV-PRD-005",
        "Imputacao",
        "Produtos cujo peso continuou nulo apos a imputacao",
        f"mediana da categoria com pelo menos {transform.MIN_OBS_MEDIANA_CATEGORIA} observacoes",
        sem_peso if sem_peso is not None else "nao mensuravel",
        APROVADO if sem_peso == 0 else ALERTA,
        "nulo sem possibilidade de imputacao permanece nulo",
    )


def _validar_geolocalizacao(val: Validador) -> None:
    """Confere a flag de coordenada contra a caixa que a propria silver usou."""
    caixa = (
        f"latitude is null or longitude is null "
        f"or latitude not between {transform.LAT_MIN_BRASIL} and {transform.LAT_MAX_BRASIL} "
        f"or longitude not between {transform.LNG_MIN_BRASIL} and {transform.LNG_MAX_BRASIL}"
    )
    val.zero(
        "SLV-GEO-001",
        "Geolocalizacao",
        "flag_coordenada_invalida coerente com a caixa delimitadora do Brasil",
        f"select count(*) from slv_geolocalizacao_pontos "
        f"where flag_coordenada_invalida is distinct from ({caixa})",
        detalhes=(
            f"caixa lat [{transform.LAT_MIN_BRASIL}, {transform.LAT_MAX_BRASIL}] "
            f"lng [{transform.LNG_MIN_BRASIL}, {transform.LNG_MAX_BRASIL}], "
            "importada de src/silver/transform.py"
        ),
    )
    val.zero(
        "SLV-GEO-002",
        "Geolocalizacao",
        "geolocalizacao_cep sem prefixo formado so por ponto invalido",
        "select count(*) from slv_geolocalizacao_cep where qtd_pontos_validos < 1",
    )

    prefixos_origem = val.contar(
        "select count(distinct geolocation_zip_code_prefix) from brz_olist_geolocalizacao"
    )
    prefixos_silver = val.contar("select count(*) from slv_geolocalizacao_cep")
    descartados = prefixos_origem - prefixos_silver
    val.registrar(
        "SLV-GEO-003",
        "Geolocalizacao",
        "Prefixos de CEP sem nenhuma coordenada valida",
        "0 (ou documentado como alerta)",
        descartados,
        APROVADO if descartados == 0 else ALERTA,
        f"{prefixos_silver} de {prefixos_origem} prefixos agregados; "
        "nenhum ponto e inventado para os demais",
    )

    invalidos = val.contar(
        "select count(*) from slv_geolocalizacao_pontos where flag_coordenada_invalida"
    )
    val.registrar(
        "SLV-GEO-004",
        "Geolocalizacao",
        "Pontos com coordenada fora do territorio brasileiro",
        "sinalizados, nunca removidos",
        invalidos,
        APROVADO if invalidos == 0 else ALERTA,
        "preservados em geolocalizacao_pontos para auditoria",
    )


# --------------------------------------------------------------------------
# INT-* -- integracao municipal
# --------------------------------------------------------------------------


def validar_integracao(val: Validador) -> None:
    faltando = [t for t in GRAO_INTEGRACAO if f"slv_{t}" not in val.disponivel]
    if len(faltando) == len(GRAO_INTEGRACAO):
        val.pular(
            "INT-EST-001",
            "Integracao municipal",
            "Saidas da etapa de integracao municipal",
            "etapa ainda nao executada; rode python -m src.run_pipeline --etapa integracao",
        )
        return

    val.igual(
        "INT-EST-001",
        "Integracao municipal",
        "Saidas da integracao presentes em data/silver/",
        len(GRAO_INTEGRACAO),
        len(GRAO_INTEGRACAO) - len(faltando),
        detalhes=("ausente(s): " + ", ".join(faltando)) if faltando else "",
    )

    _validar_chaves(val, "INT-PK", dict(GRAO_INTEGRACAO), "slv_")
    _validar_metodos_match(val)
    _validar_distancias(val)
    _validar_cobertura_socioeconomica(val)


def _validar_metodos_match(val: Validador) -> None:
    integracao = _modulo_integracao()
    raio = integracao.RAIO_ACEITE_KM if integracao else 50.0
    de_para = integracao.DE_PARA if integracao else RAIZ / "de_para_municipios.csv"

    vocabulario = ", ".join(f"'{m}'" for m in VOCABULARIO_MATCH)
    mapas = (
        ("clientes", "municipios_cliente", "customer_id", "clientes"),
        ("vendedores", "municipios_vendedor", "seller_id", "vendedores"),
    )

    for indice, (rotulo, tabela, chave, origem) in enumerate(mapas, start=1):
        if f"slv_{tabela}" not in val.disponivel:
            continue
        view = f"slv_{tabela}"

        val.zero(
            f"INT-MET-{indice:03d}",
            "Integracao municipal",
            f"{tabela}.metodo_match dentro do vocabulario do contrato 5.3",
            f"select count(*) from {view} where metodo_match not in ({vocabulario})",
        )
        val.zero(
            f"INT-MET-{indice + 2:03d}",
            "Integracao municipal",
            f"{tabela}: nao_resolvido implica cod_ibge nulo, resolvido implica preenchido",
            f"select count(*) from {view} where "
            "(metodo_match = 'nao_resolvido' and cod_ibge is not null) or "
            "(metodo_match <> 'nao_resolvido' and cod_ibge is null)",
        )
        val.zero(
            f"INT-MET-{indice + 4:03d}",
            "Integracao municipal",
            f"{tabela}: distancia_match_km preenchida apenas no metodo geografico",
            f"select count(*) from {view} where "
            "distancia_match_km is not null and metodo_match <> 'geografico'",
        )
        val.zero(
            f"INT-MET-{indice + 6:03d}",
            "Integracao municipal",
            f"{tabela}: fallback geografico dentro de {raio} km",
            f"select count(*) from {view} where metodo_match = 'geografico' "
            f"and (distancia_match_km is null or distancia_match_km > {raio})",
        )
        val.zero(
            f"INT-FK-{indice:03d}",
            "Integracao municipal",
            f"{tabela}.cod_ibge existe no cadastro do IBGE",
            f"select count(*) from {view} m "
            "left join slv_municipios g on g.cod_ibge = m.cod_ibge "
            "where m.cod_ibge is not null and g.cod_ibge is null",
        )

        # O match tem de respeitar a UF (plano 14.3) -- com uma excecao real:
        # o de-para existe justamente para corrigir UF errada no cadastro do
        # Olist ("blumenau/SP" -> Blumenau/SC), cada linha com evidencia em
        # de_para_municipios.csv. Exigir UF igual nele reprovaria exatamente o
        # que ele conserta.
        val.zero(
            f"INT-UF-{indice:03d}",
            "Integracao municipal",
            f"{tabela}: match respeita a UF de origem (de_para isento)",
            f"select count(*) from {view} m "
            f"join slv_{origem} o using ({chave}) "
            "join slv_municipios g on g.cod_ibge = m.cod_ibge "
            "where m.metodo_match not in ('de_para', 'nao_resolvido') "
            "and upper(trim(o.uf)) <> g.uf",
        )

        nao_resolvidos = val.contar(
            f"select count(*) from {view} where metodo_match = 'nao_resolvido'"
        )
        total = val.contar(f"select count(*) from {view}")
        taxa = (total - nao_resolvidos) / total if total else 0.0
        val.registrar(
            f"INT-TAXA-{indice:03d}",
            "Integracao municipal",
            f"Taxa de match de {rotulo}",
            "documentada; nao resolvido gera alerta (plano 14.4)",
            f"{taxa:.4%} ({total - nao_resolvidos} de {total})",
            APROVADO if nao_resolvidos == 0 else ALERTA,
            f"{nao_resolvidos} nao resolvido(s), listados em municipios_nao_resolvidos.csv",
        )

    # O de-para cruza UF de proposito; conferir que a evidencia existe.
    if "slv_municipios_vendedor" in val.disponivel and de_para.exists():
        linhas_de_para = sum(
            1
            for linha in de_para.read_text(encoding="utf-8").splitlines()[1:]
            if linha.strip()
        )
        usados = val.contar(
            "select count(*) from slv_municipios_vendedor where metodo_match = 'de_para'"
        ) + val.contar(
            "select count(*) from slv_municipios_cliente where metodo_match = 'de_para'"
        )
        val.registrar(
            "INT-DEP-001",
            "Integracao municipal",
            "Correcoes de_para aplicadas tem entrada versionada com justificativa",
            f"{linhas_de_para} entrada(s) em de_para_municipios.csv",
            f"{usados} entidade(s) corrigida(s)",
            APROVADO if linhas_de_para > 0 or usados == 0 else REPROVADO,
            "de-para vazio com correcoes aplicadas significa dado nao reproduzivel",
        )


def _validar_distancias(val: Validador) -> None:
    if "slv_distancias_vendedor_cliente" in val.disponivel:
        val.zero(
            "INT-DIST-001",
            "Distancias",
            "Nenhuma distancia negativa (plano 15)",
            "select count(*) from slv_distancias_vendedor_cliente where distancia_km < 0",
        )
        pares = val.contar(
            "select count(*) from (select distinct i.seller_id, p.customer_id "
            "from slv_itens_pedido i join slv_pedidos p using (order_id))"
        )
        val.igual(
            "INT-DIST-002",
            "Distancias",
            "1 linha por par (seller_id, customer_id) presente em itens_pedido",
            pares,
            val.contar("select count(*) from slv_distancias_vendedor_cliente"),
        )
        nulas = val.contar(
            "select count(*) from slv_distancias_vendedor_cliente where distancia_km is null"
        )
        val.registrar(
            "INT-DIST-003",
            "Distancias",
            "Pares sem distancia calculada",
            "permitido quando falta coordenada valida (plano 15)",
            nulas,
            APROVADO if nulas == 0 else ALERTA,
            "distancia nula nunca vira zero",
        )

    if "slv_distancias_itens" in val.disponivel:
        val.zero(
            "INT-DIST-004",
            "Distancias",
            "distancias_itens: flag coerente com a distancia",
            "select count(*) from slv_distancias_itens where "
            "flag_distancia_calculada is distinct from (distancia_km is not null)",
        )
        itens = val.contar("select count(*) from slv_itens_pedido")
        val.igual(
            "INT-DIST-005",
            "Distancias",
            "distancias_itens preserva o grao de itens_pedido",
            itens,
            val.contar("select count(*) from slv_distancias_itens"),
        )
        sem = val.contar(
            "select count(*) from slv_distancias_itens where not flag_distancia_calculada"
        )
        motivos = val.con.execute(
            "select motivo_distancia_ausente, count(*) from slv_distancias_itens "
            "where motivo_distancia_ausente is not null group by 1 order by 2 desc"
        ).fetchall()
        val.registrar(
            "INT-DIST-006",
            "Distancias",
            "Itens sem distancia calculada",
            "permitido, com motivo registrado",
            sem,
            APROVADO if sem == 0 else ALERTA,
            "; ".join(f"{m}: {n}" for m, n in motivos),
        )


def _validar_cobertura_socioeconomica(val: Validador) -> None:
    """Plano 14.5: ausencia de indicador nunca vira zero."""
    if "slv_municipios" not in val.disponivel:
        return
    sem_populacao = val.contar(
        "select count(*) from slv_municipios where populacao is null"
    )
    sem_pib = val.contar(
        "select count(*) from slv_municipios where pib_per_capita is null"
    )
    detalhes = ""
    if sem_populacao or sem_pib:
        faltantes = val.con.execute(
            "select cod_ibge, municipio, uf from slv_municipios "
            "where populacao is null or pib_per_capita is null order by cod_ibge limit 10"
        ).fetchall()
        detalhes = "; ".join(f"{c} {m}/{u}" for c, m, u in faltantes)

    val.registrar(
        "INT-SOC-001",
        "Cobertura socioeconomica",
        "Municipios sem populacao estimada",
        "ausencia permanece nula (plano 14.5)",
        sem_populacao,
        APROVADO if sem_populacao == 0 else ALERTA,
        detalhes,
    )
    val.registrar(
        "INT-SOC-002",
        "Cobertura socioeconomica",
        "Municipios sem PIB per capita",
        "ausencia permanece nula (plano 14.5)",
        sem_pib,
        APROVADO if sem_pib == 0 else ALERTA,
        detalhes,
    )

    if "slv_municipios_cliente" in val.disponivel:
        clientes = val.contar(
            "select count(*) from slv_municipios_cliente m "
            "join slv_municipios g on g.cod_ibge = m.cod_ibge "
            "where g.populacao is null or g.pib_per_capita is null"
        )
        val.registrar(
            "INT-SOC-003",
            "Cobertura socioeconomica",
            "Clientes em municipio sem indicador",
            "informativo (plano 14.5)",
            clientes,
            APROVADO if clientes == 0 else ALERTA,
        )


# --------------------------------------------------------------------------
# CTR-* -- conformidade com o contrato de dados
# --------------------------------------------------------------------------


def validar_contrato(val: Validador) -> None:
    """Diverge do contrato onde a implementacao seguiu outro caminho.

    Por decisao do grupo estes testes so reportam: renomear coluna agora
    quebraria a integracao municipal, que ja consome os nomes atuais. O valor
    esta em a gold descobrir a divergencia aqui, e nao no meio da carga
    dimensional.
    """
    faltando = [
        f"{contrato} (a silver grava {real})"
        for contrato, real in CONTRATO_ARQUIVOS.items()
        if not (DIR_SILVER / contrato).exists()
    ]
    val.registrar(
        "CTR-NOME-001",
        "Contrato de dados",
        "Arquivos com o nome fixado em contratos_dados.md secao 4",
        f"{len(CONTRATO_ARQUIVOS)} arquivo(s)",
        f"{len(CONTRATO_ARQUIVOS) - len(faltando)} com o nome do contrato",
        APROVADO if not faltando else ALERTA,
        "; ".join(faltando),
    )

    renomeadas: list[str] = []
    ausentes: list[str] = []
    for secao, (tabela, mapa) in CONTRATO_COLUNAS.items():
        view = f"slv_{tabela}"
        if view not in val.disponivel:
            continue
        colunas = _colunas(val.con, view)
        for coluna_contrato, coluna_real in mapa.items():
            if coluna_contrato in colunas:
                continue
            if coluna_real is None:
                ausentes.append(f"{secao}.{coluna_contrato}")
            else:
                renomeadas.append(f"{secao}: {coluna_contrato} -> {coluna_real}")

    val.registrar(
        "CTR-COL-001",
        "Contrato de dados",
        "Colunas do contrato ausentes sem equivalente na silver",
        0,
        len(ausentes),
        APROVADO if not ausentes else ALERTA,
        "; ".join(ausentes),
    )
    val.registrar(
        "CTR-COL-002",
        "Contrato de dados",
        "Colunas do contrato gravadas com outro nome",
        0,
        len(renomeadas),
        APROVADO if not renomeadas else ALERTA,
        "; ".join(renomeadas),
    )

    divergentes: list[str] = []
    for tabela, coluna, tipo_contrato, secao in CONTRATO_TIPOS:
        view = f"slv_{tabela}"
        if view not in val.disponivel:
            continue
        colunas = _colunas(val.con, view)
        real = colunas.get(coluna)
        if real is None:
            continue
        if real.replace(" ", "").upper() != tipo_contrato.replace(" ", "").upper():
            divergentes.append(f"{secao} {tabela}.{coluna}: {tipo_contrato} -> {real}")
    val.registrar(
        "CTR-TIPO-001",
        "Contrato de dados",
        "Tipos conforme o contrato (monetario DECIMAL(12,2), secao 1)",
        0,
        len(divergentes),
        APROVADO if not divergentes else ALERTA,
        "; ".join(divergentes),
    )

    for id_, descricao, esperado, encontrado in CONTRATO_REGRAS:
        val.registrar(
            id_, "Contrato de dados", descricao, esperado, encontrado, ALERTA
        )

    if "slv_municipios" in val.disponivel:
        municipios = val.contar("select count(*) from slv_municipios")
        val.registrar(
            "CTR-CARD-001",
            "Contrato de dados",
            "Cardinalidade do cadastro municipal",
            "5570 (contrato secoes 3 e 6.2)",
            municipios,
            APROVADO if municipios == 5570 else ALERTA,
            "o excedente e Boa Esperanca do Norte (5101837/MT), instalado depois de "
            "2017; a dim_geografia precisa decidir se ele entra",
        )


# --------------------------------------------------------------------------
# REP-* -- reprodutibilidade
# --------------------------------------------------------------------------


def validar_reprodutibilidade(val: Validador) -> None:
    """Pega a camada meio fresca, meio velha.

    O orquestrador pula etapa cujo modulo nao existe e segue. Se a saida
    daquela etapa continuar em disco de uma execucao anterior, a silver fica
    inconsistente sem nenhum aviso -- e a gold consome a mistura.
    """
    import importlib.util

    from .. import run_pipeline

    etapas_ausentes = [
        etapa
        for etapa in run_pipeline.ETAPAS
        if importlib.util.find_spec(etapa.modulo) is None
    ]
    orfaos: list[str] = []
    for etapa in etapas_ausentes:
        if etapa.nome == "integracao":
            orfaos += [
                t for t in GRAO_INTEGRACAO if (DIR_SILVER / f"{t}.parquet").exists()
            ]

    val.igual(
        "REP-001",
        "Reprodutibilidade",
        "Nenhum artefato em disco de etapa cujo modulo nao existe",
        0,
        len(orfaos),
        detalhes=(
            "artefato orfao, nao reproduzivel pelo checkout atual: " + ", ".join(orfaos)
        )
        if orfaos
        else (
            "etapa(s) ainda nao escrita(s): "
            + ", ".join(e.nome for e in etapas_ausentes)
            if etapas_ausentes
            else ""
        ),
    )

    tabelas_transform = [
        DIR_SILVER / f"{t}.parquet"
        for t in GRAO_SILVER
        if (DIR_SILVER / f"{t}.parquet").exists()
    ]
    tabelas_integracao = [
        DIR_SILVER / f"{t}.parquet"
        for t in GRAO_INTEGRACAO
        if (DIR_SILVER / f"{t}.parquet").exists()
    ]
    if tabelas_transform and tabelas_integracao:
        mais_nova_transform = max(p.stat().st_mtime for p in tabelas_transform)
        atrasadas = [
            p.name
            for p in tabelas_integracao
            if p.stat().st_mtime < mais_nova_transform
        ]
        val.igual(
            "REP-002",
            "Reprodutibilidade",
            "Saidas da integracao nao sao mais antigas que as da silver",
            0,
            len(atrasadas),
            # Sem carimbo de tempo no detalhe: o plano de qualidade (secao 18)
            # compara dois relatorios seguidos, e um mtime no texto faria toda
            # execucao parecer diferente da anterior.
            detalhes=(
                "gerada(s) antes da ultima execucao da silver: " + ", ".join(atrasadas)
            )
            if atrasadas
            else f"{len(tabelas_integracao)} saida(s) da integracao conferida(s)",
        )

    integracao = _modulo_integracao()
    de_para = integracao.DE_PARA if integracao else RAIZ / "de_para_municipios.csv"

    if de_para.exists():
        cabecalho = de_para.read_text(encoding="utf-8").splitlines()[0].split(",")
        esperado = ["cidade_origem", "uf_origem", "cod_ibge", "justificativa"]
        val.igual(
            "REP-003",
            "Reprodutibilidade",
            "de_para_municipios.csv com as colunas do contrato 5.4",
            ", ".join(esperado),
            ", ".join(c.strip() for c in cabecalho),
            detalhes="cabecalho divergente faz a etapa de integracao quebrar no binder",
        )


# --------------------------------------------------------------------------
# Relatorios
# --------------------------------------------------------------------------


def _milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def desfecho(resultados: list[Resultado]) -> str:
    """Plano de qualidade secao 20."""
    if any(r.status == REPROVADO for r in resultados):
        return "REPROVADO"
    if any(r.status in (ALERTA, NAO_EXECUTADO) for r in resultados):
        return "APROVADO COM ALERTAS"
    return "APROVADO"


def _resumo(resultados: list[Resultado]) -> dict[str, int]:
    return {
        "executados": len(resultados),
        "aprovados": sum(1 for r in resultados if r.status == APROVADO),
        "alertas": sum(1 for r in resultados if r.status == ALERTA),
        "reprovados": sum(1 for r in resultados if r.status == REPROVADO),
        "nao_executados": sum(1 for r in resultados if r.status == NAO_EXECUTADO),
    }


def gravar_json(val: Validador, geral: str) -> None:
    DIR_SILVER.mkdir(parents=True, exist_ok=True)
    conteudo = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "resultado_geral": geral,
        "resumo": _resumo(val.resultados),
        "contagens": val.contagens,
        "testes": [r.como_dict() for r in val.resultados],
    }
    RELATORIO_JSON.write_text(
        json.dumps(conteudo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def gravar_markdown(val: Validador, geral: str) -> None:
    resumo = _resumo(val.resultados)
    partes: list[str] = [
        "# Relatorio de validacao -- bronze e silver",
        "",
        "> Gerado por `src/qualidade/validar_camadas.py` a cada execucao do",
        "> pipeline. Nao editar a mao.",
        "",
        f"Gerado em {datetime.now():%Y-%m-%d %H:%M:%S}.",
        "",
        "## Resumo executivo",
        "",
        f"- Testes executados: {resumo['executados']}",
        f"- Aprovados: {resumo['aprovados']}",
        f"- Alertas: {resumo['alertas']}",
        f"- Reprovados: {resumo['reprovados']}",
        f"- Nao executados: {resumo['nao_executados']}",
        f"- **Resultado geral: {geral}**",
        "",
        "## Contagens por camada",
        "",
    ]

    for camada in ("bronze", "silver"):
        linhas = val.contagens.get(camada, {})
        if not linhas:
            continue
        partes += [
            f"### {camada.capitalize()} -- {len(linhas)} tabela(s), "
            f"{_milhar(sum(linhas.values()))} linhas",
            "",
            "| Tabela | Linhas |",
            "| --- | ---: |",
        ]
        partes += [f"| `{t}` | {_milhar(n)} |" for t, n in sorted(linhas.items())]
        partes.append("")

    partes += ["## Testes", "", "| ID | Verificacao | Esperado | Encontrado | Status |",
               "| --- | --- | --- | --- | --- |"]
    for r in val.resultados:
        partes.append(
            f"| `{r.id}` | {r.descricao} | {r.esperado} | {r.encontrado} | {r.status} |"
        )
    partes.append("")

    atencao = [r for r in val.resultados if r.status != APROVADO]
    partes += ["## Casos que exigem atencao", ""]
    if not atencao:
        partes += ["Nenhum. Todos os testes aprovados.", ""]
    else:
        for r in atencao:
            partes.append(f"### `{r.id}` -- {r.status}")
            partes.append("")
            partes.append(f"{r.descricao}. Esperado {r.esperado}, encontrado {r.encontrado}.")
            if r.detalhes:
                partes.append("")
                partes.append(r.detalhes)
            partes.append("")

    DIR_DOCS.mkdir(parents=True, exist_ok=True)
    RELATORIO_MD.write_text("\n".join(partes), encoding="utf-8")


# --------------------------------------------------------------------------
# Entrada
# --------------------------------------------------------------------------


def executar() -> list[Resultado]:
    con = duckdb.connect()
    val = Validador(con)

    preparar(val)
    _inventariar(val)
    validar_bronze(val)
    validar_silver(val)
    validar_integracao(val)
    validar_contrato(val)
    validar_reprodutibilidade(val)

    geral = desfecho(val.resultados)
    resumo = _resumo(val.resultados)

    # O relatorio e gravado antes de a execucao cair: o plano de qualidade
    # (secao 20) exige que a falha chegue documentada, nao so no traceback.
    gravar_json(val, geral)
    gravar_markdown(val, geral)

    log.info(
        "validacao: %d teste(s) | %d aprovado(s), %d alerta(s), %d reprovado(s) | %s",
        resumo["executados"],
        resumo["aprovados"],
        resumo["alertas"],
        resumo["reprovados"],
        geral,
    )
    log.info("relatorio em %s", RELATORIO_MD.relative_to(RAIZ))

    if resumo["reprovados"]:
        reprovados = [r for r in val.resultados if r.status == REPROVADO]
        detalhe = "; ".join(
            f"{r.id} ({r.descricao}): esperado {r.esperado}, encontrado {r.encontrado}"
            for r in reprovados
        )
        raise ValueError(
            f"validacao das camadas bronze/silver reprovada em {len(reprovados)} "
            f"teste(s) -- {detalhe}. Relatorio completo em "
            f"{RELATORIO_MD.relative_to(RAIZ)}."
        )
    return val.resultados


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    executar()


if __name__ == "__main__":
    main()
