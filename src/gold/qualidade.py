"""Verificacoes executadas antes da publicacao e pela etapa qualidade."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import duckdb

TABELAS = {
    'dim_tempo': 'sk_tempo', 'dim_produto': 'sk_produto',
    'dim_cliente': 'sk_cliente', 'dim_vendedor': 'sk_vendedor',
    'dim_geografia': 'sk_geografia', 'dim_pagamento': 'sk_pagamento',
    'fato_pedido': 'order_id', 'fato_item_pedido': 'order_id, order_item_id',
}


def assinaturas(con):
    """SHA-256 do conteudo ordenado; nao dos bytes fisicos do DuckDB."""
    resultado = {}
    for tabela, chave in TABELAS.items():
        h = hashlib.sha256()
        cursor = con.execute(f'SELECT * FROM {tabela} ORDER BY {chave}')
        h.update(repr(cursor.description).encode())
        while linhas := cursor.fetchmany(10000):
            for linha in linhas:
                h.update((repr(linha) + '\n').encode('utf-8'))
        resultado[tabela] = h.hexdigest()
    return resultado


def analisar(con):
    resultados = []
    def conferir(nome, esperado, encontrado):
        resultados.append({'teste': nome, 'esperado': str(esperado), 'encontrado': str(encontrado),
                           'status': 'APROVADO' if esperado == encontrado else 'REPROVADO'})
    def zero(nome, sql):
        conferir(nome, 0, con.execute(sql).fetchone()[0])
    contagens = {t: con.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in TABELAS}
    for tabela, chave in TABELAS.items():
        zero(f'Grao {tabela}', f'SELECT count(*) FROM (SELECT {chave} FROM {tabela} GROUP BY {chave} HAVING count(*)>1)')
        if tabela.startswith('dim_'):
            conferir(f'Membro desconhecido {tabela}', 1, con.execute(f'SELECT count(*) FROM {tabela} WHERE {chave}=0').fetchone()[0])
    for tabela, origem, natural in (
        ('dim_produto','produtos','product_id'), ('dim_cliente','clientes','customer_unique_id'),
        ('dim_vendedor','vendedores','seller_id'), ('dim_geografia','geografia_integrada','cod_ibge'),
    ):
        conferir(f'Cobertura {tabela}', con.execute(f'SELECT count(DISTINCT {natural})+1 FROM slv_{origem}').fetchone()[0], contagens[tabela])
        zero(f'Chave natural {tabela}', f'SELECT count(*) FROM (SELECT {natural} FROM {tabela} GROUP BY {natural} HAVING count(*)>1)')
    zero('Combinacao natural de pagamento', 'SELECT count(*) FROM (SELECT tipo_pagamento,quantidade_parcelas FROM dim_pagamento GROUP BY ALL HAVING count(*)>1)')
    zero('Total do item', 'SELECT count(*) FROM fato_item_pedido WHERE valor_total_item IS DISTINCT FROM valor_produto + valor_frete')
    zero('Entregas elegiveis', "SELECT count(*) FROM fato_pedido WHERE NOT flag_entregue AND (dias_ate_entrega IS NOT NULL OR dias_atraso IS NOT NULL OR flag_atraso IS NOT NULL)")
    zero('Flag de atraso', 'SELECT count(*) FROM fato_pedido WHERE flag_atraso IS DISTINCT FROM (dias_atraso > 0)')
    zero('Dominio da nota', 'SELECT count(*) FROM fato_pedido WHERE nota_avaliacao NOT BETWEEN 1 AND 5')
    zero('Contexto do pedido nos itens', """SELECT count(*) FROM fato_item_pedido i LEFT JOIN fato_pedido p USING(order_id)
        WHERE p.order_id IS NULL OR i.sk_cliente<>p.sk_cliente OR i.sk_geo_cliente<>p.sk_geo_cliente
        OR i.sk_tempo_compra<>p.sk_tempo_compra OR i.sk_tempo_entrega<>p.sk_tempo_entrega
        OR i.sk_pagamento<>p.sk_pagamento OR i.nota_avaliacao IS DISTINCT FROM p.nota_avaliacao""")
    fks = con.execute('''SELECT table_name, constraint_column_names[1], referenced_table,
        referenced_column_names[1] FROM duckdb_constraints() WHERE constraint_type='FOREIGN KEY' ''').fetchall()
    conferir('Quantidade de FKs declaradas', 12, len(fks))
    usos = {}
    for tabela, fk, dimensao, pk in fks:
        zero(f'FK {tabela}.{fk}', f'''SELECT count(*) FROM {tabela} f LEFT JOIN {dimensao} d
            ON f.{fk}=d.{pk} WHERE d.{pk} IS NULL''')
        usos[f'{tabela}.{fk}'] = con.execute(f'SELECT count(*) FROM {tabela} WHERE {fk}=0').fetchone()[0]
    for fato, silver in [('fato_item_pedido','itens_pedido'),('fato_pedido','pedidos')]:
        conferir(f'Contagem {fato}', con.execute(f'SELECT count(*) FROM slv_{silver}').fetchone()[0], contagens[fato])
    for coluna, origem in [('valor_produto','preco_produto'),('valor_frete','valor_frete'),('valor_total_item','valor_total_item')]:
        zero(f'Valor por item {coluna}', f'''SELECT count(*) FROM fato_item_pedido f
            FULL JOIN slv_itens_pedido s ON f.order_id=s.order_id AND f.order_item_id=s.item_pedido_id
            WHERE f.order_id IS NULL OR s.order_id IS NULL OR f.{coluna} IS DISTINCT FROM s.{origem}''')
        conferir(f'Soma {coluna}', con.execute(f'SELECT sum({origem}) FROM slv_itens_pedido').fetchone()[0],
                 con.execute(f'SELECT sum({coluna}) FROM fato_item_pedido').fetchone()[0])
    for coluna, origem in [('valor_produtos','valor_produto'),('valor_frete','valor_frete'),('valor_total_pedido','valor_total_item')]:
        zero(f'Agregacao por pedido {coluna}', f'''WITH totais AS (
            SELECT order_id, CASE WHEN count({origem})=count(*) THEN sum({origem}) END AS valor
            FROM fato_item_pedido GROUP BY order_id)
            SELECT count(*) FROM fato_pedido p LEFT JOIN totais t USING(order_id)
            WHERE p.{coluna} IS DISTINCT FROM CASE WHEN t.order_id IS NULL THEN 0 ELSE t.valor END''')
    zero('Pagamento nao multiplicado', '''SELECT count(*) FROM fato_pedido f LEFT JOIN slv_pagamentos p USING(order_id)
        WHERE f.valor_total_pago IS DISTINCT FROM p.valor_total_pago''')
    zero('Avaliacao por pedido preservada', '''SELECT count(*) FROM fato_pedido f LEFT JOIN slv_avaliacoes a USING(order_id)
        WHERE f.nota_avaliacao IS DISTINCT FROM a.nota_review''')
    zero('Prazos preservados', '''SELECT count(*) FROM fato_pedido f JOIN slv_pedidos p USING(order_id)
        WHERE f.dias_ate_entrega IS DISTINCT FROM p.dias_ate_entrega
           OR f.dias_atraso IS DISTINCT FROM p.dias_atraso OR f.flag_atraso IS DISTINCT FROM p.flag_atraso''')
    zero('Distancia oficial preservada', '''SELECT count(*) FROM fato_item_pedido f JOIN slv_distancias_itens d USING(order_id,order_item_id)
        WHERE f.distancia_km IS DISTINCT FROM d.distancia_km''')
    zero('Cliente persistente e endereco por pedido', '''SELECT count(*) FROM fato_pedido f
        JOIN slv_pedidos p USING(order_id) JOIN slv_clientes c USING(customer_id)
        JOIN slv_clientes_municipios m USING(customer_id)
        JOIN dim_cliente dc ON dc.sk_cliente=f.sk_cliente
        JOIN dim_geografia g ON g.sk_geografia=f.sk_geo_cliente
        WHERE dc.customer_unique_id IS DISTINCT FROM c.customer_unique_id
           OR g.cod_ibge IS DISTINCT FROM m.cod_ibge''')
    zero('Tempo de compra', '''SELECT count(*) FROM fato_pedido f JOIN slv_pedidos p USING(order_id)
        JOIN dim_tempo t ON t.sk_tempo=f.sk_tempo_compra WHERE t.data_completa IS DISTINCT FROM p.ts_compra::DATE''')
    zero('Tempo de entrega', '''SELECT count(*) FROM fato_pedido f JOIN slv_pedidos p USING(order_id)
        JOIN dim_tempo t ON t.sk_tempo=f.sk_tempo_entrega
        WHERE t.data_completa IS DISTINCT FROM CASE WHEN p.status_pedido='delivered' THEN p.ts_entrega_cliente::DATE END''')
    cobertura = {}
    for entidade in ('clientes','vendedores'):
        cobertura[entidade] = dict(con.execute(f'SELECT metodo_match,count(*) FROM slv_{entidade}_municipios GROUP BY 1 ORDER BY 1').fetchall())
    return {'contagens': contagens, 'testes': resultados, 'uso_desconhecidos': usos,
            'match_municipal': cobertura, 'assinaturas': assinaturas(con),
            'erros': [r['teste'] for r in resultados if r['status']=='REPROVADO']}


def gravar_relatorio(relatorio, gold):
    (gold / 'qualidade.json').write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding='utf-8')
    texto = '# Qualidade da Gold\n\n' + ('APROVADO' if not relatorio['erros'] else 'REPROVADO') + '\n\n'
    texto += '| Tabela | Linhas |\n| --- | ---: |\n'
    texto += ''.join(f'| {t} | {n} |\n' for t,n in relatorio['contagens'].items())
    texto += '\n| Verificacao | Esperado | Encontrado | Resultado |\n| --- | --- | --- | --- |\n'
    texto += ''.join(f"| {r['teste']} | {r['esperado']} | {r['encontrado']} | {r['status']} |\n" for r in relatorio['testes'])
    texto += '\n## Uso de membros desconhecidos\n\n```json\n' + json.dumps(relatorio['uso_desconhecidos'],indent=2) + '\n```\n'
    texto += '\n## Cobertura municipal por metodo\n\n```json\n' + json.dumps(relatorio['match_municipal'],indent=2) + '\n```\n'
    texto += '\nAssinaturas ordenadas por tabela em `qualidade.json`; comparar duas cargas para comprovar reproducibilidade.\n'
    (gold / 'qualidade.md').write_text(texto,encoding='utf-8')


def executar():
    from .dimensional import DIR_GOLD, DIR_SILVER
    with duckdb.connect(str(DIR_GOLD / 'dw.duckdb'), read_only=True) as con:
        # Views temporarias permitem validar o DW sem modificar o arquivo publicado.
        from ..silver.contrato_gold import ENTRADAS, verificar
        erros = verificar(con, DIR_SILVER)
        if erros:
            raise ValueError('; '.join(erros))
        for nome in ENTRADAS:
            caminho = (DIR_SILVER / f'{nome}.parquet').as_posix().replace("'", "''")
            con.execute(f"CREATE TEMP VIEW slv_{nome} AS SELECT * FROM read_parquet('{caminho}')")
        relatorio = analisar(con)
    gravar_relatorio(relatorio, DIR_GOLD)
    if relatorio['erros']:
        raise ValueError('Gold reprovada: ' + '; '.join(relatorio['erros']))


if __name__ == '__main__':
    executar()
