"""Contrato Silver -> Gold v2: nomes fisicos, tipos e nulidade obrigatorios.

Um sufixo ! marca coluna NOT NULL. Colunas extras sao permitidas.
Regras e traducao para o modelo dimensional: docs/contrato_entrada_gold.md.
"""

VERSAO = 2

# tabela: (chave de grao, grupos de colunas por tipo)
ENTRADAS = {
    "pedidos": (("order_id",), {
        "VARCHAR": "order_id! customer_id! status_pedido! ano_mes_compra",
        "TIMESTAMP": "ts_compra ts_aprovacao ts_envio_transportadora ts_entrega_cliente ts_estimativa_entrega",
        "BIGINT": "dias_ate_entrega dias_atraso",
        "BOOLEAN": "flag_entrega_ausente! flag_atraso",
    }),
    "itens_pedido": (("order_id", "item_pedido_id"), {
        "VARCHAR": "order_id! product_id seller_id faixa_preco",
        "INTEGER": "item_pedido_id!",
        "TIMESTAMP": "ts_limite_envio",
        "DECIMAL(18,2)": "preco_produto valor_frete valor_total_item",
        "BOOLEAN": "flag_frete_outlier",
    }),
    "produtos": (("product_id",), {
        "VARCHAR": "product_id! categoria_produto! categoria_produto_ingles!",
        "DOUBLE": "peso_g comprimento_cm altura_cm largura_cm",
        "BOOLEAN": "flag_categoria_sem_traducao! flag_peso_imputado! flag_dimensoes_imputadas!",
    }),
    "clientes": (("customer_id",), {
        "VARCHAR": "customer_id! customer_unique_id! cep_prefixo cidade uf",
    }),
    "vendedores": (("seller_id",), {
        "VARCHAR": "seller_id! cep_prefixo cidade uf",
    }),
    "pagamentos": (("order_id",), {
        "VARCHAR": "order_id! tipo_pagamento_predominante",
        "INTEGER": "parcelas_tipo_predominante",
        "BIGINT": "qtd_transacoes! qtd_metodos_distintos!",
        "DECIMAL(18,2)": "valor_total_pago",
    }),
    "avaliacoes": (("order_id",), {
        "VARCHAR": "order_id! review_id! titulo_review mensagem_review",
        "INTEGER": "nota_review",
        "TIMESTAMP": "ts_criacao_review ts_resposta_review",
        "BOOLEAN": "flag_avaliacao_duplicada_pedido!",
    }),
    "geografia_integrada": (("cod_ibge",), {
        "VARCHAR": "cod_ibge! municipio! municipio_normalizado! uf! nome_uf regiao porte_municipio!",
        "BIGINT": "populacao_estimada",
        "INTEGER": "ano_referencia_indicadores",
        "DECIMAL(18,2)": "pib_per_capita",
        "DOUBLE": "latitude_representativa longitude_representativa",
    }),
    "distancias_itens": (("order_id", "order_item_id"), {
        "VARCHAR": "order_id! motivo_distancia_ausente",
        "INTEGER": "order_item_id!",
        "DOUBLE": "distancia_km",
        "BOOLEAN": "flag_distancia_calculada!",
    }),
}

for entidade, chave, sufixo in (
    ("clientes", "customer_id", "cliente"),
    ("vendedores", "seller_id", "vendedor"),
):
    ENTRADAS[f"{entidade}_municipios"] = ((chave,), {
        "VARCHAR": f"{chave}! cod_ibge metodo_match! cidade_original cidade_normalizada uf motivo_nao_resolvido",
        "DOUBLE": f"distancia_match_km latitude_{sufixo} longitude_{sufixo}",
    })


def colunas(tabela):
    """Itera (nome, tipo DuckDB exato, aceita_nulo)."""
    for tipo, nomes in ENTRADAS[tabela][1].items():
        for nome in nomes.split():
            yield nome.rstrip("!"), tipo, not nome.endswith("!")


def verificar(con, diretorio):
    """Retorna violacoes concretas; nao converte tipos nem altera arquivos."""
    erros = []
    for tabela, (chave, _) in ENTRADAS.items():
        caminho = diretorio / f"{tabela}.parquet"
        if not caminho.is_file():
            erros.append(f"Arquivo obrigatorio ausente: {caminho}")
            continue
        relacao = con.read_parquet(str(caminho))
        reais = dict(zip(relacao.columns, map(str, relacao.types)))
        for nome, tipo, aceita_nulo in colunas(tabela):
            if reais.get(nome) != tipo:
                erros.append(f"{tabela}.{nome}: esperado {tipo}, encontrado {reais.get(nome, 'ausente')}")
            if nome in reais and not aceita_nulo:
                n = relacao.filter(f'"{nome}" IS NULL').count('*').fetchone()[0]
                if n:
                    erros.append(f"{tabela}.{nome}: {n} nulos proibidos")
        if all(c in reais for c in chave):
            campos = ', '.join(f'"{c}"' for c in chave)
            duplicadas = relacao.aggregate(f"{campos}, count(*) as n", campos).filter('n > 1').count('*').fetchone()[0]
            if duplicadas:
                erros.append(f"{tabela}: {duplicadas} chaves duplicadas no grao {chave}")
    return erros
