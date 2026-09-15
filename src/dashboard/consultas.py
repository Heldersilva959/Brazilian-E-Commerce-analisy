"""Consultas do dashboard: unica fonte e o DW, aberto em modo somente leitura."""
from datetime import date
from pathlib import Path
import duckdb

DW = Path(__file__).resolve().parents[2] / 'data/gold/dw.duckdb'


def conectar(caminho=DW):
    if not caminho.is_file():
        raise FileNotFoundError('DW ausente. Execute python -m src.run_pipeline antes de abrir o dashboard.')
    return duckdb.connect(str(caminho), read_only=True)


def linhas(con,sql,params=None):
    cursor=con.execute(sql,params or [])
    nomes=[c[0] for c in cursor.description]
    return [dict(zip(nomes,r)) for r in cursor.fetchall()]


def opcoes(caminho=DW):
    with conectar(caminho) as con:
        datas=con.execute('''SELECT min(t.data_completa),max(t.data_completa)
            FROM fato_pedido p JOIN dim_tempo t ON t.sk_tempo=p.sk_tempo_compra''').fetchone()
        ufs=[r[0] for r in con.execute('''SELECT DISTINCT g.uf FROM fato_pedido p
            JOIN dim_geografia g ON g.sk_geografia=p.sk_geo_cliente ORDER BY 1''').fetchall()]
        return {'inicio':datas[0],'fim':datas[1],'ufs':ufs}


def analisar(inicio,fim,uf='Todas',caminho=DW):
    inicio=date.fromisoformat(inicio)
    fim=date.fromisoformat(fim)
    if inicio>fim:
        raise ValueError('A data inicial deve ser anterior ou igual à data final.')
    params=[inicio,fim,uf,uf]
    base='''WITH pedidos AS (
        SELECT p.*, t.data_completa,t.ano_mes,g.uf,g.porte_municipio
        FROM fato_pedido p
        JOIN dim_tempo t ON t.sk_tempo=p.sk_tempo_compra
        JOIN dim_geografia g ON g.sk_geografia=p.sk_geo_cliente
        WHERE t.data_completa BETWEEN ? AND ? AND (?='Todas' OR g.uf=?)
    ) '''
    with conectar(caminho) as con:
        def consulta(sql):
            return linhas(con,base+sql,params)
        resumo=consulta('''SELECT count(*) AS pedidos_filtrados,
            count(*) FILTER(WHERE status_pedido='delivered') AS entregues,
            sum(valor_total_pedido) FILTER(WHERE status_pedido='delivered') AS valor_entregue,
            avg(valor_total_pedido) FILTER(WHERE status_pedido='delivered') AS ticket,
            count(valor_total_pedido) FILTER(WHERE status_pedido='delivered') AS base_ticket,
            100.0*sum(valor_frete) FILTER(WHERE status_pedido='delivered') /
              nullif(sum(valor_total_pedido) FILTER(WHERE status_pedido='delivered'),0) AS percentual_frete,
            avg(dias_ate_entrega) FILTER(WHERE status_pedido='delivered') AS prazo,
            count(dias_ate_entrega) FILTER(WHERE status_pedido='delivered') AS base_prazo,
            100.0*count(*) FILTER(WHERE status_pedido='delivered' AND flag_atraso) /
              nullif(count(flag_atraso) FILTER(WHERE status_pedido='delivered'),0) AS atraso,
            count(flag_atraso) FILTER(WHERE status_pedido='delivered') AS base_atraso,
            count(*) FILTER(WHERE status_pedido='delivered' AND flag_atraso) AS atrasados,
            avg(nota_avaliacao) AS nota,
            count(nota_avaliacao) AS avaliados,
            100.0*count(*) FILTER(WHERE nota_avaliacao>=4)/nullif(count(nota_avaliacao),0) AS positivas,
            100.0*count(*) FILTER(WHERE nota_avaliacao<=2)/nullif(count(nota_avaliacao),0) AS negativas,
            100.0*count(nota_avaliacao)/nullif(count(*),0) AS cobertura
            FROM pedidos''')[0]
        resumo.update(consulta('''SELECT avg(i.distancia_km) AS distancia,count(i.distancia_km) AS base_distancia
            FROM fato_item_pedido i JOIN pedidos p USING(order_id) WHERE p.status_pedido='delivered' ''')[0])
        return {'resumo':resumo,
          'mensal':consulta('''SELECT ano_mes AS nome,sum(valor_total_pedido) AS valor,count(*) AS base
            FROM pedidos WHERE status_pedido='delivered' GROUP BY 1 ORDER BY 1'''),
          'categorias':consulta('''SELECT pr.categoria_pt AS nome,sum(i.valor_total_item) AS valor,count(*) AS base
            FROM fato_item_pedido i JOIN pedidos p USING(order_id)
            JOIN dim_produto pr USING(sk_produto) WHERE p.status_pedido='delivered'
            GROUP BY 1 ORDER BY valor DESC NULLS LAST,nome LIMIT 10'''),
          'porte':consulta('''SELECT porte_municipio AS nome,avg(valor_total_pedido) AS valor,count(valor_total_pedido) AS base
            FROM pedidos WHERE status_pedido='delivered' GROUP BY 1
            ORDER BY CASE porte_municipio WHEN 'Pequeno' THEN 1 WHEN 'Médio' THEN 2 WHEN 'Grande' THEN 3 ELSE 4 END'''),
          'atraso_uf':consulta('''SELECT uf AS nome,100.0*count(*) FILTER(WHERE flag_atraso)/count(*) AS valor,count(*) AS base
            FROM pedidos WHERE status_pedido='delivered' AND flag_atraso IS NOT NULL
            GROUP BY 1 ORDER BY valor DESC,nome'''),
          'prazo_mensal':consulta('''SELECT ano_mes AS nome,avg(dias_ate_entrega) AS valor,count(*) AS base
            FROM pedidos WHERE status_pedido='delivered' AND dias_ate_entrega IS NOT NULL GROUP BY 1 ORDER BY 1'''),
          'notas':consulta('''SELECT cast(nota_avaliacao AS VARCHAR)||' estrelas' AS nome,count(*) AS valor,count(*) AS base
            FROM pedidos WHERE nota_avaliacao IS NOT NULL GROUP BY nota_avaliacao ORDER BY nota_avaliacao'''),
          'nota_atraso':consulta('''SELECT CASE WHEN flag_atraso THEN 'Com atraso' ELSE 'No prazo' END AS nome,
            avg(nota_avaliacao) AS valor,count(*) AS base FROM pedidos
            WHERE status_pedido='delivered' AND flag_atraso IS NOT NULL AND nota_avaliacao IS NOT NULL
            GROUP BY 1 ORDER BY 1'''),
          'filtros':{'inicio':inicio,'fim':fim,'uf':uf}}
