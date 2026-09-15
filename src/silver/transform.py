"""Camada Silver: limpeza, tipagem e agregacoes sobre a bronze.

Le os parquets da bronze (colunas de origem como string, mais as colunas de
linhagem `_fonte`, `_arquivo_origem` e `_data_ingestao`), tipa e limpa,
e grava os parquets da silver em `data/silver/`. Nao faz join entre pedidos,
itens, pagamentos e avaliacoes -- isso e responsabilidade da gold, para nao
multiplicar linhas antes da hora.

As regras de negocio (categoria ausente, imputacao por mediana, tipo de
pagamento predominante, desempate de avaliacoes, faixas de preco, outlier de
frete e a agregacao de geolocalizacao por prefixo de CEP) estao documentadas
com os numeros reais do dataset em `docs/silver_contrato.md`.

Os nomes de arquivo esperados da bronze (`BRONZE_ESPERADA`) sao uma proposta
deste modulo, a confirmar com quem implementa a bronze; se os nomes reais
forem outros, so e preciso ajustar esse dicionario.

Execucao (depois que a bronze existir):

    .venv\\Scripts\\python.exe -m src.silver.transform
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[2]
DIR_BRONZE = RAIZ / "data" / "bronze"
DIR_SILVER = RAIZ / "data" / "silver"

# Arquivo esperado da bronze para cada entidade -- ver docs/silver_contrato.md
# secao 1. Ajustar aqui se a bronze nomear diferente.
BRONZE_ESPERADA: dict[str, Path] = {
    "pedidos": DIR_BRONZE / "pedidos.parquet",
    "itens_pedido": DIR_BRONZE / "itens_pedido.parquet",
    "pagamentos": DIR_BRONZE / "pagamentos.parquet",
    "avaliacoes": DIR_BRONZE / "avaliacoes.parquet",
    "produtos": DIR_BRONZE / "produtos.parquet",
    "clientes": DIR_BRONZE / "clientes.parquet",
    "vendedores": DIR_BRONZE / "vendedores.parquet",
    "geolocalizacao": DIR_BRONZE / "geolocalizacao.parquet",
    "traducao_categorias": DIR_BRONZE / "traducao_categorias.parquet",
}

# Caixa delimitadora aproximada do territorio brasileiro, usada so para
# sinalizar coordenadas claramente invalidas antes da mediana por CEP.
LAT_MIN_BRASIL, LAT_MAX_BRASIL = -34.0, 6.0
LNG_MIN_BRASIL, LNG_MAX_BRASIL = -75.0, -33.0

# Minimo de observacoes nao nulas na categoria para confiar na mediana de
# peso/dimensoes; abaixo disso mantem nulo e loga a ocorrencia (ver
# docs/silver_contrato.md secao 7).
MIN_OBS_MEDIANA_CATEGORIA = 5

log = logging.getLogger("silver_transform")


def _tabelas_requeridas(nomes: list[str]) -> dict[str, Path]:
    """Confere que os parquets pedidos existem antes de qualquer SQL.

    Interrompe com nome e caminho esperado do primeiro arquivo ausente,
    conforme o README exige para fontes obrigatorias.
    """
    faltando = [
        (nome, BRONZE_ESPERADA[nome]) for nome in nomes if not BRONZE_ESPERADA[nome].exists()
    ]
    if faltando:
        detalhes = "; ".join(f"{nome} -> {caminho}" for nome, caminho in faltando)
        raise FileNotFoundError(
            f"Arquivo(s) obrigatorio(s) da bronze ausente(s): {detalhes}"
        )
    return {nome: BRONZE_ESPERADA[nome] for nome in nomes}


def _gravar(con: duckdb.DuckDBPyConnection, relacao_sql: str, destino: Path) -> int:
    DIR_SILVER.mkdir(parents=True, exist_ok=True)
    con.execute(
        f"COPY ({relacao_sql}) TO '{destino.as_posix()}' (FORMAT PARQUET)"
    )
    total = con.execute(f"SELECT count(*) FROM ({relacao_sql})").fetchone()[0]
    log.info("gravado %s (%d linhas)", destino.relative_to(RAIZ), total)
    return total


def transformar_pedidos(con: duckdb.DuckDBPyConnection) -> Path:
    arquivos = _tabelas_requeridas(["pedidos"])
    sql = f"""
        with base as (
            select
                order_id,
                customer_id,
                order_status as status_pedido,
                cast(order_purchase_timestamp as timestamp) as ts_compra,
                cast(order_approved_at as timestamp) as ts_aprovacao,
                cast(order_delivered_carrier_date as timestamp) as ts_envio_transportadora,
                cast(order_delivered_customer_date as timestamp) as ts_entrega_cliente,
                cast(order_estimated_delivery_date as timestamp) as ts_estimativa_entrega
            from read_parquet('{arquivos["pedidos"].as_posix()}')
        ),
        derivado as (
            select
                *,
                (status_pedido = 'delivered' and ts_entrega_cliente is null)
                    as flag_entrega_ausente,
                case
                    when status_pedido = 'delivered' and ts_entrega_cliente is not null
                        then date_diff('day', ts_compra, ts_entrega_cliente)
                end as dias_ate_entrega,
                case
                    when status_pedido = 'delivered' and ts_entrega_cliente is not null
                        then date_diff('day', ts_estimativa_entrega, ts_entrega_cliente)
                end as dias_atraso,
                strftime(ts_compra, '%Y-%m') as ano_mes_compra
            from base
        )
        select
            order_id,
            customer_id,
            status_pedido,
            ts_compra,
            ts_aprovacao,
            ts_envio_transportadora,
            ts_entrega_cliente,
            ts_estimativa_entrega,
            flag_entrega_ausente,
            dias_ate_entrega,
            dias_atraso,
            case when dias_atraso is not null then dias_atraso > 0 end as flag_atraso,
            ano_mes_compra
        from derivado
    """
    return _gravar(con, sql, DIR_SILVER / "pedidos.parquet")


def transformar_itens_pedido(con: duckdb.DuckDBPyConnection) -> Path:
    arquivos = _tabelas_requeridas(["itens_pedido"])
    sql = f"""
        with base as (
            select
                order_id,
                cast(order_item_id as integer) as item_pedido_id,
                product_id,
                seller_id,
                cast(shipping_limit_date as timestamp) as ts_limite_envio,
                cast(price as decimal(12, 2)) as preco_produto,
                cast(freight_value as decimal(12, 2)) as valor_frete
            from read_parquet('{arquivos["itens_pedido"].as_posix()}')
        ),
        cercas as (
            select
                quantile_cont(valor_frete, 0.25) as frete_q1,
                quantile_cont(valor_frete, 0.75) as frete_q3
            from base
        )
        select
            b.order_id,
            b.item_pedido_id,
            b.product_id,
            b.seller_id,
            b.ts_limite_envio,
            b.preco_produto,
            b.valor_frete,
            (b.preco_produto + b.valor_frete) as valor_total_item,
            case
                when b.preco_produto <= 39.90 then 'baixo'
                when b.preco_produto <= 74.99 then 'medio_baixo'
                when b.preco_produto <= 134.90 then 'medio_alto'
                else 'alto'
            end as faixa_preco,
            (b.valor_frete > c.frete_q3 + 1.5 * (c.frete_q3 - c.frete_q1))
                as flag_frete_outlier
        from base b
        cross join cercas c
    """
    return _gravar(con, sql, DIR_SILVER / "itens_pedido.parquet")


def transformar_pagamentos(con: duckdb.DuckDBPyConnection) -> Path:
    arquivos = _tabelas_requeridas(["pagamentos"])
    sql = f"""
        with base as (
            select
                order_id,
                payment_type,
                cast(payment_installments as integer) as payment_installments,
                cast(payment_value as decimal(12, 2)) as payment_value
            from read_parquet('{arquivos["pagamentos"].as_posix()}')
        ),
        por_tipo as (
            select
                order_id,
                payment_type,
                sum(payment_value) as valor_tipo,
                max(payment_installments) as parcelas_tipo
            from base
            group by 1, 2
        ),
        ranqueado as (
            select
                *,
                -- Empate: valor_tipo igual vira ordem alfabetica de payment_type
                -- (regra estavel documentada em docs/silver_contrato.md; nao ha
                -- empate real nos dados atuais).
                row_number() over (
                    partition by order_id
                    order by valor_tipo desc, payment_type asc
                ) as posicao
            from por_tipo
        ),
        agregado_pedido as (
            select
                order_id,
                sum(payment_value) as valor_total_pago,
                count(*) as qtd_transacoes,
                count(distinct payment_type) as qtd_metodos_distintos
            from base
            group by 1
        )
        select
            a.order_id,
            a.valor_total_pago,
            a.qtd_transacoes,
            a.qtd_metodos_distintos,
            r.payment_type as tipo_pagamento_predominante,
            r.parcelas_tipo as parcelas_tipo_predominante
        from agregado_pedido a
        join ranqueado r on r.order_id = a.order_id and r.posicao = 1
    """
    return _gravar(con, sql, DIR_SILVER / "pagamentos.parquet")


def transformar_avaliacoes(con: duckdb.DuckDBPyConnection) -> Path:
    arquivos = _tabelas_requeridas(["avaliacoes"])
    sql = f"""
        with base as (
            select
                review_id,
                order_id,
                cast(review_score as integer) as nota_review,
                review_comment_title as titulo_review,
                review_comment_message as mensagem_review,
                cast(review_creation_date as timestamp) as ts_criacao_review,
                cast(review_answer_timestamp as timestamp) as ts_resposta_review
            from read_parquet('{arquivos["avaliacoes"].as_posix()}')
        ),
        contagem as (
            select order_id, count(*) as qtd_avaliacoes
            from base
            group by 1
        ),
        ranqueado as (
            select
                b.*,
                row_number() over (
                    partition by b.order_id
                    order by
                        b.ts_criacao_review desc,
                        b.ts_resposta_review desc,
                        b.review_id desc
                ) as posicao
            from base b
        )
        select
            r.order_id,
            r.review_id,
            r.nota_review,
            r.titulo_review,
            r.mensagem_review,
            r.ts_criacao_review,
            r.ts_resposta_review,
            (c.qtd_avaliacoes > 1) as flag_avaliacao_duplicada_pedido
        from ranqueado r
        join contagem c on c.order_id = r.order_id
        where r.posicao = 1
    """
    return _gravar(con, sql, DIR_SILVER / "avaliacoes.parquet")


def transformar_produtos(con: duckdb.DuckDBPyConnection) -> Path:
    arquivos = _tabelas_requeridas(["produtos", "traducao_categorias"])
    sql = f"""
        with base as (
            select
                product_id,
                coalesce(nullif(trim(product_category_name), ''), 'nao_informado')
                    as categoria_produto,
                cast(product_weight_g as double) as peso_g,
                cast(product_length_cm as double) as comprimento_cm,
                cast(product_height_cm as double) as altura_cm,
                cast(product_width_cm as double) as largura_cm
            from read_parquet('{arquivos["produtos"].as_posix()}')
        ),
        traducao as (
            select
                product_category_name as categoria_produto,
                product_category_name_english as categoria_produto_ingles
            from read_parquet('{arquivos["traducao_categorias"].as_posix()}')
        ),
        medianas_categoria as (
            select
                categoria_produto,
                count(peso_g) as n_peso,
                median(peso_g) as mediana_peso_g,
                count(comprimento_cm) as n_dim,
                median(comprimento_cm) as mediana_comprimento_cm,
                median(altura_cm) as mediana_altura_cm,
                median(largura_cm) as mediana_largura_cm
            from base
            group by 1
        )
        select
            b.product_id,
            b.categoria_produto,
            coalesce(t.categoria_produto_ingles, b.categoria_produto)
                as categoria_produto_ingles,
            (b.categoria_produto != 'nao_informado' and t.categoria_produto_ingles is null)
                as flag_categoria_sem_traducao,
            coalesce(
                b.peso_g,
                case when m.n_peso >= {MIN_OBS_MEDIANA_CATEGORIA} then m.mediana_peso_g end
            ) as peso_g,
            coalesce(
                b.comprimento_cm,
                case when m.n_dim >= {MIN_OBS_MEDIANA_CATEGORIA} then m.mediana_comprimento_cm end
            ) as comprimento_cm,
            coalesce(
                b.altura_cm,
                case when m.n_dim >= {MIN_OBS_MEDIANA_CATEGORIA} then m.mediana_altura_cm end
            ) as altura_cm,
            coalesce(
                b.largura_cm,
                case when m.n_dim >= {MIN_OBS_MEDIANA_CATEGORIA} then m.mediana_largura_cm end
            ) as largura_cm,
            (b.peso_g is null) as flag_peso_imputado,
            (b.comprimento_cm is null or b.altura_cm is null or b.largura_cm is null)
                as flag_dimensoes_imputadas
        from base b
        left join traducao t on t.categoria_produto = b.categoria_produto
        left join medianas_categoria m on m.categoria_produto = b.categoria_produto
    """
    return _gravar(con, sql, DIR_SILVER / "produtos.parquet")


def transformar_clientes(con: duckdb.DuckDBPyConnection) -> Path:
    arquivos = _tabelas_requeridas(["clientes"])
    sql = f"""
        select
            customer_id,
            customer_unique_id,
            customer_zip_code_prefix as cep_prefixo,
            trim(customer_city) as cidade,
            trim(customer_state) as uf
        from read_parquet('{arquivos["clientes"].as_posix()}')
    """
    return _gravar(con, sql, DIR_SILVER / "clientes.parquet")


def transformar_vendedores(con: duckdb.DuckDBPyConnection) -> Path:
    arquivos = _tabelas_requeridas(["vendedores"])
    sql = f"""
        select
            seller_id,
            seller_zip_code_prefix as cep_prefixo,
            trim(seller_city) as cidade,
            trim(seller_state) as uf
        from read_parquet('{arquivos["vendedores"].as_posix()}')
    """
    return _gravar(con, sql, DIR_SILVER / "vendedores.parquet")


def transformar_geolocalizacao(con: duckdb.DuckDBPyConnection) -> tuple[Path, Path]:
    """Grava os pontos brutos sinalizados e a mediana por prefixo de CEP.

    A mediana e o insumo esperado pelo Membro 3 para o fallback geografico
    (ver docs/silver_contrato.md secao 9): so entram nela pontos com
    coordenada dentro da caixa aproximada do Brasil.
    """
    arquivos = _tabelas_requeridas(["geolocalizacao"])
    sql_pontos = f"""
        select
            geolocation_zip_code_prefix as cep_prefixo,
            cast(geolocation_lat as double) as latitude,
            cast(geolocation_lng as double) as longitude,
            trim(geolocation_city) as cidade,
            trim(geolocation_state) as uf,
            (
                cast(geolocation_lat as double) not between {LAT_MIN_BRASIL} and {LAT_MAX_BRASIL}
                or cast(geolocation_lng as double) not between {LNG_MIN_BRASIL} and {LNG_MAX_BRASIL}
            ) as flag_coordenada_invalida
        from read_parquet('{arquivos["geolocalizacao"].as_posix()}')
    """
    destino_pontos = _gravar(con, sql_pontos, DIR_SILVER / "geolocalizacao_pontos.parquet")

    sql_cep = f"""
        with pontos as ({sql_pontos}),
        validos as (
            select * from pontos where not flag_coordenada_invalida
        ),
        moda_cidade as (
            select cep_prefixo, cidade, uf, count(*) as n,
                   row_number() over (
                       partition by cep_prefixo order by count(*) desc, cidade asc
                   ) as posicao
            from validos
            group by 1, 2, 3
        )
        select
            v.cep_prefixo,
            median(v.latitude) as latitude_mediana,
            median(v.longitude) as longitude_mediana,
            count(*) as qtd_pontos_validos,
            (
                select count(*) from pontos p
                where p.cep_prefixo = v.cep_prefixo and p.flag_coordenada_invalida
            ) as qtd_pontos_invalidos,
            max(m.cidade) filter (where m.posicao = 1) as cidade_predominante,
            max(m.uf) filter (where m.posicao = 1) as uf_predominante
        from validos v
        left join moda_cidade m on m.cep_prefixo = v.cep_prefixo
        group by v.cep_prefixo
    """
    destino_cep = _gravar(con, sql_cep, DIR_SILVER / "geolocalizacao_cep.parquet")
    return destino_pontos, destino_cep


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    con = duckdb.connect()
    transformar_pedidos(con)
    transformar_itens_pedido(con)
    transformar_pagamentos(con)
    transformar_avaliacoes(con)
    transformar_produtos(con)
    transformar_clientes(con)
    transformar_vendedores(con)
    transformar_geolocalizacao(con)


if __name__ == "__main__":
    main()
