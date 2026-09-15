-- Modelo estrela: chaves naturais unicas, SK 0 reservado para desconhecido.
CREATE TABLE dim_tempo (
 sk_tempo INTEGER PRIMARY KEY, data_completa DATE UNIQUE, dia INTEGER,
 nome_dia_semana VARCHAR, numero_dia_semana INTEGER, semana_ano INTEGER,
 mes INTEGER, nome_mes VARCHAR, trimestre INTEGER, ano INTEGER,
 ano_mes VARCHAR, fim_de_semana BOOLEAN
);
CREATE TABLE dim_cliente (
 sk_cliente INTEGER PRIMARY KEY, customer_unique_id VARCHAR UNIQUE
);
CREATE TABLE dim_produto (
 sk_produto INTEGER PRIMARY KEY, product_id VARCHAR UNIQUE,
 categoria_pt VARCHAR, categoria_en VARCHAR, peso_gramas DOUBLE,
 comprimento_cm DOUBLE, altura_cm DOUBLE, largura_cm DOUBLE, volume_cm3 DOUBLE,
 faixa_peso VARCHAR, peso_imputado BOOLEAN, dimensoes_imputadas BOOLEAN,
 flag_categoria_sem_traducao BOOLEAN
);
CREATE TABLE dim_geografia (
 sk_geografia INTEGER PRIMARY KEY, cod_ibge VARCHAR UNIQUE, municipio VARCHAR,
 uf VARCHAR, nome_uf VARCHAR, regiao VARCHAR, populacao_estimada BIGINT,
 pib_per_capita DECIMAL(18,2), porte_municipio VARCHAR,
 ano_referencia_indicadores INTEGER, latitude_representativa DOUBLE,
 longitude_representativa DOUBLE
);
CREATE TABLE dim_vendedor (
 sk_vendedor INTEGER PRIMARY KEY, seller_id VARCHAR UNIQUE, cidade VARCHAR,
 uf VARCHAR, cod_ibge VARCHAR, municipio_ibge VARCHAR, regiao VARCHAR,
 metodo_match_municipio VARCHAR
);
CREATE TABLE dim_pagamento (
 sk_pagamento INTEGER PRIMARY KEY, tipo_pagamento VARCHAR,
 quantidade_parcelas INTEGER, faixa_parcelas VARCHAR,
 UNIQUE(tipo_pagamento, quantidade_parcelas)
);
CREATE TABLE fato_pedido (
 order_id VARCHAR PRIMARY KEY,
 sk_tempo_compra INTEGER NOT NULL REFERENCES dim_tempo(sk_tempo),
 sk_tempo_entrega INTEGER NOT NULL REFERENCES dim_tempo(sk_tempo),
 sk_cliente INTEGER NOT NULL REFERENCES dim_cliente(sk_cliente),
 sk_geo_cliente INTEGER NOT NULL REFERENCES dim_geografia(sk_geografia),
 sk_pagamento INTEGER NOT NULL REFERENCES dim_pagamento(sk_pagamento),
 status_pedido VARCHAR NOT NULL, quantidade_itens BIGINT NOT NULL,
 quantidade_vendedores BIGINT NOT NULL, quantidade_produtos BIGINT NOT NULL,
 valor_produtos DECIMAL(18,2), valor_frete DECIMAL(18,2),
 valor_total_pedido DECIMAL(18,2), valor_total_pago DECIMAL(18,2),
 dias_ate_entrega BIGINT, dias_atraso BIGINT, flag_atraso BOOLEAN,
 nota_avaliacao INTEGER, flag_entregue BOOLEAN NOT NULL,
 flag_possui_avaliacao BOOLEAN NOT NULL, flag_entrega_ausente BOOLEAN NOT NULL,
 metodo_match_municipio VARCHAR NOT NULL
);
CREATE TABLE fato_item_pedido (
 order_id VARCHAR NOT NULL, order_item_id INTEGER NOT NULL,
 sk_tempo_compra INTEGER NOT NULL REFERENCES dim_tempo(sk_tempo),
 sk_tempo_entrega INTEGER NOT NULL REFERENCES dim_tempo(sk_tempo),
 sk_produto INTEGER NOT NULL REFERENCES dim_produto(sk_produto),
 sk_cliente INTEGER NOT NULL REFERENCES dim_cliente(sk_cliente),
 sk_vendedor INTEGER NOT NULL REFERENCES dim_vendedor(sk_vendedor),
 sk_geo_cliente INTEGER NOT NULL REFERENCES dim_geografia(sk_geografia),
 sk_pagamento INTEGER NOT NULL REFERENCES dim_pagamento(sk_pagamento),
 valor_produto DECIMAL(18,2), valor_frete DECIMAL(18,2), valor_total_item DECIMAL(18,2),
 dias_ate_entrega BIGINT, dias_atraso BIGINT, flag_atraso BOOLEAN,
 distancia_km DOUBLE, nota_avaliacao INTEGER, flag_outlier_frete BOOLEAN,
 faixa_preco VARCHAR, flag_distancia_calculada BOOLEAN NOT NULL,
 motivo_distancia_ausente VARCHAR,
 PRIMARY KEY(order_id, order_item_id)
);
