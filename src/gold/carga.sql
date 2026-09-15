-- Calendario deterministico: minimo de 2016-01-01 a 2018-12-31.
INSERT INTO dim_tempo
WITH datas AS (
 SELECT ts_compra::DATE AS data FROM slv_pedidos
 UNION ALL SELECT ts_entrega_cliente::DATE FROM slv_pedidos
), limites AS (
 SELECT least(DATE '2016-01-01', min(data)) AS inicio,
        greatest(DATE '2018-12-31', max(data)) AS fim FROM datas
), calendario AS (
 SELECT unnest(generate_series(inicio, fim, INTERVAL 1 DAY))::DATE AS data FROM limites
)
SELECT row_number() OVER (ORDER BY data), data, day(data),
 ['segunda-feira','terça-feira','quarta-feira','quinta-feira','sexta-feira','sábado','domingo'][isodow(data)],
 isodow(data), week(data), month(data),
 ['janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro'][month(data)],
 quarter(data), year(data), strftime(data, '%Y-%m'), isodow(data) IN (6,7)
FROM calendario;
INSERT INTO dim_tempo (sk_tempo, nome_dia_semana, nome_mes, ano_mes)
VALUES (0, 'nao_informado', 'nao_informado', 'nao_informado');

INSERT INTO dim_cliente
SELECT row_number() OVER (ORDER BY customer_unique_id), customer_unique_id
FROM (SELECT DISTINCT customer_unique_id FROM slv_clientes);
INSERT INTO dim_cliente VALUES (0, NULL);

INSERT INTO dim_produto
SELECT row_number() OVER (ORDER BY product_id), product_id,
 categoria_produto, categoria_produto_ingles, peso_g,
 comprimento_cm, altura_cm, largura_cm, comprimento_cm * altura_cm * largura_cm,
 CASE WHEN peso_g IS NULL THEN 'nao_informado' WHEN peso_g <= 1000 THEN 'ate_1kg'
      WHEN peso_g <= 5000 THEN '1_a_5kg' WHEN peso_g <= 20000 THEN '5_a_20kg'
      ELSE 'acima_20kg' END,
 flag_peso_imputado, flag_dimensoes_imputadas, flag_categoria_sem_traducao
FROM slv_produtos;
INSERT INTO dim_produto (sk_produto, categoria_pt, categoria_en, faixa_peso)
VALUES (0, 'nao_informado', 'nao_informado', 'nao_informado');

INSERT INTO dim_geografia
SELECT row_number() OVER (ORDER BY cod_ibge), cod_ibge, municipio,
 uf, nome_uf, regiao, populacao_estimada, pib_per_capita, porte_municipio,
 ano_referencia_indicadores, latitude_representativa, longitude_representativa
FROM slv_geografia_integrada;
INSERT INTO dim_geografia (sk_geografia, municipio, uf, nome_uf, regiao, porte_municipio)
VALUES (0, 'nao_informado', 'nao_informado', 'nao_informado', 'nao_informado', 'Não informado');

INSERT INTO dim_vendedor
SELECT row_number() OVER (ORDER BY v.seller_id), v.seller_id, v.cidade,
 coalesce(g.uf, v.uf), m.cod_ibge, g.municipio, g.regiao, m.metodo_match
FROM slv_vendedores v
JOIN slv_vendedores_municipios m USING(seller_id)
LEFT JOIN slv_geografia_integrada g USING(cod_ibge);
INSERT INTO dim_vendedor (sk_vendedor, cidade, uf, municipio_ibge, regiao, metodo_match_municipio)
VALUES (0, 'nao_informado', 'nao_informado', 'nao_informado', 'nao_informado', 'nao_resolvido');

INSERT INTO dim_pagamento
SELECT row_number() OVER (ORDER BY tipo_pagamento_predominante NULLS LAST, parcelas_tipo_predominante NULLS LAST),
 tipo_pagamento_predominante, parcelas_tipo_predominante,
 CASE WHEN parcelas_tipo_predominante IS NULL OR parcelas_tipo_predominante < 1 THEN 'nao_informado'
      WHEN parcelas_tipo_predominante = 1 THEN '1_parcela'
      WHEN parcelas_tipo_predominante <= 3 THEN '2_a_3'
      WHEN parcelas_tipo_predominante <= 6 THEN '4_a_6'
      WHEN parcelas_tipo_predominante <= 12 THEN '7_a_12' ELSE 'acima_12' END
FROM (SELECT DISTINCT tipo_pagamento_predominante, parcelas_tipo_predominante
      FROM slv_pagamentos
      WHERE tipo_pagamento_predominante IS NOT NULL OR parcelas_tipo_predominante IS NOT NULL);
INSERT INTO dim_pagamento VALUES (0, NULL, NULL, 'nao_informado');

-- Contexto por pedido: nenhuma relacao um-para-muitos participa deste join.
CREATE TEMP VIEW contexto_pedido AS
SELECT p.*, coalesce(tc.sk_tempo,0) AS sk_tempo_compra,
 coalesce(te.sk_tempo,0) AS sk_tempo_entrega,
 coalesce(c.sk_cliente,0) AS sk_cliente, coalesce(g.sk_geografia,0) AS sk_geo_cliente,
 coalesce(pg.sk_pagamento,0) AS sk_pagamento,
 a.nota_review AS nota_avaliacao, a.order_id IS NOT NULL AS flag_possui_avaliacao,
 pa.valor_total_pago, m.metodo_match AS metodo_match_municipio
FROM slv_pedidos p
JOIN slv_clientes cli USING(customer_id)
JOIN slv_clientes_municipios m USING(customer_id)
LEFT JOIN dim_cliente c USING(customer_unique_id)
LEFT JOIN dim_geografia g ON g.cod_ibge = m.cod_ibge
LEFT JOIN dim_tempo tc ON tc.data_completa = p.ts_compra::DATE
LEFT JOIN dim_tempo te ON te.data_completa = p.ts_entrega_cliente::DATE AND p.status_pedido = 'delivered'
LEFT JOIN slv_pagamentos pa USING(order_id)
LEFT JOIN dim_pagamento pg ON pg.tipo_pagamento IS NOT DISTINCT FROM pa.tipo_pagamento_predominante
 AND pg.quantidade_parcelas IS NOT DISTINCT FROM pa.parcelas_tipo_predominante
LEFT JOIN slv_avaliacoes a ON a.order_id = p.order_id;

INSERT INTO fato_pedido
WITH agregado AS (
 SELECT order_id, count(*) AS quantidade_itens,
 count(DISTINCT seller_id) AS quantidade_vendedores, count(DISTINCT product_id) AS quantidade_produtos,
 -- Uma soma incompleta nao deve parecer um total conhecido.
 CASE WHEN count(preco_produto) = count(*) THEN sum(preco_produto) END AS valor_produtos,
 CASE WHEN count(valor_frete) = count(*) THEN sum(valor_frete) END AS valor_frete,
 CASE WHEN count(valor_total_item) = count(*) THEN sum(valor_total_item) END AS valor_total_pedido
 FROM slv_itens_pedido GROUP BY order_id
)
SELECT p.order_id, p.sk_tempo_compra, p.sk_tempo_entrega, p.sk_cliente, p.sk_geo_cliente, p.sk_pagamento,
 p.status_pedido, coalesce(i.quantidade_itens,0), coalesce(i.quantidade_vendedores,0), coalesce(i.quantidade_produtos,0),
 CASE WHEN i.order_id IS NULL THEN 0 ELSE i.valor_produtos END,
 CASE WHEN i.order_id IS NULL THEN 0 ELSE i.valor_frete END,
 CASE WHEN i.order_id IS NULL THEN 0 ELSE i.valor_total_pedido END,
 p.valor_total_pago, p.dias_ate_entrega, p.dias_atraso, p.flag_atraso, p.nota_avaliacao,
 p.status_pedido = 'delivered', p.flag_possui_avaliacao, p.flag_entrega_ausente, p.metodo_match_municipio
FROM contexto_pedido p LEFT JOIN agregado i USING(order_id);

INSERT INTO fato_item_pedido
SELECT i.order_id, i.item_pedido_id, p.sk_tempo_compra, p.sk_tempo_entrega,
 coalesce(pr.sk_produto,0), p.sk_cliente, coalesce(v.sk_vendedor,0), p.sk_geo_cliente, p.sk_pagamento,
 i.preco_produto, i.valor_frete, i.valor_total_item,
 p.dias_ate_entrega, p.dias_atraso, p.flag_atraso, d.distancia_km, p.nota_avaliacao,
 i.flag_frete_outlier, i.faixa_preco, d.flag_distancia_calculada, d.motivo_distancia_ausente
FROM slv_itens_pedido i
JOIN fato_pedido p USING(order_id)
LEFT JOIN dim_produto pr USING(product_id)
LEFT JOIN dim_vendedor v USING(seller_id)
JOIN slv_distancias_itens d ON d.order_id = i.order_id AND d.order_item_id = i.item_pedido_id;
