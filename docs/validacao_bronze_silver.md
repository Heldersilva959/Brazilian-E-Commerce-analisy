# Relatorio de validacao -- bronze e silver

> Gerado por `src/qualidade/validar_camadas.py` a cada execucao do
> pipeline. Nao editar a mao.

Gerado em 2026-09-15 16:41:15.

## Resumo executivo

- Testes executados: 114
- Aprovados: 104
- Alertas: 10
- Reprovados: 0
- Nao executados: 0
- **Resultado geral: APROVADO COM ALERTAS**

## Contagens por camada

### Bronze -- 11 tabela(s), 1.562.064 linhas

| Tabela | Linhas |
| --- | ---: |
| `ibge_municipios` | 5.571 |
| `olist_avaliacoes` | 99.224 |
| `olist_clientes` | 99.441 |
| `olist_geolocalizacao` | 1.000.163 |
| `olist_itens_pedido` | 112.650 |
| `olist_pagamentos` | 103.886 |
| `olist_pedidos` | 99.441 |
| `olist_produtos` | 32.951 |
| `olist_traducao_categoria` | 71 |
| `olist_vendedores` | 3.095 |
| `socioeconomico_municipios` | 5.571 |

### Silver -- 17 tabela(s), 1.993.738 linhas

| Tabela | Linhas |
| --- | ---: |
| `avaliacoes` | 98.673 |
| `clientes` | 99.441 |
| `clientes_municipios` | 99.441 |
| `distancias_itens` | 112.650 |
| `distancias_vendedor_cliente` | 100.010 |
| `geografia_integrada` | 5.571 |
| `geolocalizacao_cep` | 19.010 |
| `geolocalizacao_pontos` | 1.000.163 |
| `itens_pedido` | 112.650 |
| `municipios` | 5.571 |
| `municipios_cliente` | 99.441 |
| `municipios_vendedor` | 3.095 |
| `pagamentos` | 99.440 |
| `pedidos` | 99.441 |
| `produtos` | 32.951 |
| `vendedores` | 3.095 |
| `vendedores_municipios` | 3.095 |

## Testes

| ID | Verificacao | Esperado | Encontrado | Status |
| --- | --- | --- | --- | --- |
| `BRZ-EST-001` | Tabelas da bronze presentes em data/bronze/ | 11 | 11 | APROVADO |
| `BRZ-EST-002` | Colunas de linhagem presentes em todas as tabelas | 0 | 0 | APROVADO |
| `BRZ-EST-003` | Colunas de linhagem com o tipo do contrato secao 3 | 0 | 0 | APROVADO |
| `BRZ-EST-004` | Toda coluna de dado e VARCHAR (contrato secao 3) | 0 | 0 | APROVADO |
| `BRZ-EST-005` | Nenhum NULL em coluna de dado: a bronze preserva '' (contrato secao 2) | 0 | 0 | APROVADO |
| `BRZ-LIN-001` | _linha_origem cobre 1..N sem buraco nem repeticao | 0 | 0 | APROVADO |
| `BRZ-LIN-002` | _fonte dentro de olist / sidra / ibge_api | 0 | 0 | APROVADO |
| `BRZ-CNT-001` | Linhas do parquet iguais as do _manifesto.json | 0 | 0 | APROVADO |
| `BRZ-CNT-002` | Linhas do parquet iguais a recontagem da origem em data/raw/ | 0 | 0 | APROVADO |
| `BRZ-CNT-003` | sha256 da origem igual ao registrado no manifesto | 0 | 0 | APROVADO |
| `SLV-EST-001` | Tabelas da silver presentes em data/silver/ | 10 | 10 | APROVADO |
| `SLV-EST-002` | Colunas obrigatorias presentes em cada tabela da silver | 0 | 0 | APROVADO |
| `SLV-PK-001` | pedidos: 1 linha por (order_id) | 0 | 0 | APROVADO |
| `SLV-PK-NUL-001` | pedidos: chave (order_id) nao nula | 0 | 0 | APROVADO |
| `SLV-PK-002` | itens_pedido: 1 linha por (order_id, item_pedido_id) | 0 | 0 | APROVADO |
| `SLV-PK-NUL-002` | itens_pedido: chave (order_id, item_pedido_id) nao nula | 0 | 0 | APROVADO |
| `SLV-PK-003` | pagamentos: 1 linha por (order_id) | 0 | 0 | APROVADO |
| `SLV-PK-NUL-003` | pagamentos: chave (order_id) nao nula | 0 | 0 | APROVADO |
| `SLV-PK-004` | avaliacoes: 1 linha por (order_id) | 0 | 0 | APROVADO |
| `SLV-PK-NUL-004` | avaliacoes: chave (order_id) nao nula | 0 | 0 | APROVADO |
| `SLV-PK-005` | produtos: 1 linha por (product_id) | 0 | 0 | APROVADO |
| `SLV-PK-NUL-005` | produtos: chave (product_id) nao nula | 0 | 0 | APROVADO |
| `SLV-PK-006` | clientes: 1 linha por (customer_id) | 0 | 0 | APROVADO |
| `SLV-PK-NUL-006` | clientes: chave (customer_id) nao nula | 0 | 0 | APROVADO |
| `SLV-PK-007` | vendedores: 1 linha por (seller_id) | 0 | 0 | APROVADO |
| `SLV-PK-NUL-007` | vendedores: chave (seller_id) nao nula | 0 | 0 | APROVADO |
| `SLV-PK-009` | geolocalizacao_cep: 1 linha por (cep_prefixo) | 0 | 0 | APROVADO |
| `SLV-PK-NUL-009` | geolocalizacao_cep: chave (cep_prefixo) nao nula | 0 | 0 | APROVADO |
| `SLV-PK-010` | municipios: 1 linha por (cod_ibge) | 0 | 0 | APROVADO |
| `SLV-PK-NUL-010` | municipios: chave (cod_ibge) nao nula | 0 | 0 | APROVADO |
| `SLV-FK-001` | itens_pedido.order_id sem correspondente em pedidos.order_id | 0 | 0 | APROVADO |
| `SLV-FK-002` | itens_pedido.product_id sem correspondente em produtos.product_id | 0 | 0 | APROVADO |
| `SLV-FK-003` | itens_pedido.seller_id sem correspondente em vendedores.seller_id | 0 | 0 | APROVADO |
| `SLV-FK-004` | pedidos.customer_id sem correspondente em clientes.customer_id | 0 | 0 | APROVADO |
| `SLV-FK-005` | pagamentos.order_id sem correspondente em pedidos.order_id | 0 | 0 | APROVADO |
| `SLV-FK-006` | avaliacoes.order_id sem correspondente em pedidos.order_id | 0 | 0 | APROVADO |
| `SLV-GRAO-001` | pedidos: mesma contagem de olist_pedidos | 99441 | 99441 | APROVADO |
| `SLV-GRAO-002` | itens_pedido: mesma contagem de olist_itens_pedido | 112650 | 112650 | APROVADO |
| `SLV-GRAO-003` | produtos: mesma contagem de olist_produtos | 32951 | 32951 | APROVADO |
| `SLV-GRAO-004` | clientes: mesma contagem de olist_clientes | 99441 | 99441 | APROVADO |
| `SLV-GRAO-005` | vendedores: mesma contagem de olist_vendedores | 3095 | 3095 | APROVADO |
| `SLV-GRAO-006` | geolocalizacao_pontos: mesma contagem de olist_geolocalizacao | 1000163 | 1000163 | APROVADO |
| `SLV-GRAO-007` | municipios: mesma contagem de ibge_municipios | 5571 | 5571 | APROVADO |
| `SLV-GRAO-008` | pagamentos: 1 linha por order_id distinto de olist_pagamentos | 99440 | 99440 | APROVADO |
| `SLV-GRAO-009` | avaliacoes: 1 linha por order_id distinto de olist_avaliacoes | 98673 | 98673 | APROVADO |
| `SLV-REC-001` | Soma do valor dos produtos: bronze x silver | 13591643.70 | 13591643.70 | APROVADO |
| `SLV-REC-002` | Soma do valor do frete: bronze x silver | 2251909.54 | 2251909.54 | APROVADO |
| `SLV-REC-003` | Soma do valor pago: bronze x silver | 16008872.12 | 16008872.12 | APROVADO |
| `SLV-REC-004` | valor_total_item diferente de preco_produto + valor_frete | 0 | 0 | APROVADO |
| `SLV-NEG-001` | ts_compra nunca nulo (contrato 4.1) | 0 | 0 | APROVADO |
| `SLV-NEG-002` | ts_estimativa_entrega nunca nulo (contrato 4.1) | 0 | 0 | APROVADO |
| `SLV-NEG-003` | Pedido nao entregue sem metrica de prazo preenchida | 0 | 0 | APROVADO |
| `SLV-NEG-004` | flag_atraso coerente com o sinal de dias_atraso | 0 | 0 | APROVADO |
| `SLV-NEG-005` | dias_ate_entrega nunca negativo | 0 | 0 | APROVADO |
| `SLV-NEG-006` | Pedidos 'delivered' sem data real de entrega | documentado como alerta (plano 11.3) | 8 | ALERTA |
| `SLV-NEG-007` | flag_entrega_ausente marca so 'delivered' sem data real de entrega | 0 | 0 | APROVADO |
| `SLV-DOM-001` | nota_review entre 1 e 5, sem nulo (contrato 4.7) | 0 | 0 | APROVADO |
| `SLV-DOM-002` | faixa_preco dentro das quatro faixas do silver_contrato 4 | 0 | 0 | APROVADO |
| `SLV-DOM-003` | clientes.cep_prefixo com 5 digitos e zero a esquerda preservado | 0 | 0 | APROVADO |
| `SLV-DOM-004` | vendedores.cep_prefixo com 5 digitos e zero a esquerda preservado | 0 | 0 | APROVADO |
| `SLV-DOM-005` | geolocalizacao_cep.cep_prefixo com 5 digitos e zero a esquerda preservado | 0 | 0 | APROVADO |
| `SLV-DOM-006` | porte_municipio dentro das faixas do contrato 4.9 | 0 | 0 | APROVADO |
| `SLV-PRD-001` | Produto sem categoria recebe 'nao_informado', nunca nulo (contrato 4.3) | 0 | 0 | APROVADO |
| `SLV-PRD-002` | flag_peso_imputado nunca marcada com peso_g nulo | 0 | 0 | APROVADO |
| `SLV-PRD-003` | flag_dimensoes_imputadas nunca marcada com dimensao nula | 0 | 0 | APROVADO |
| `SLV-PRD-004` | Produtos com categoria 'nao_informado' | documentado (plano 16) | 610 | ALERTA |
| `SLV-PRD-005` | Produtos cujo peso continuou nulo apos a imputacao | mediana da categoria com pelo menos 5 observacoes | 0 | APROVADO |
| `SLV-GEO-001` | flag_coordenada_invalida coerente com a caixa delimitadora do Brasil | 0 | 0 | APROVADO |
| `SLV-GEO-002` | geolocalizacao_cep sem prefixo formado so por ponto invalido | 0 | 0 | APROVADO |
| `SLV-GEO-003` | Prefixos de CEP sem nenhuma coordenada valida | 0 (ou documentado como alerta) | 5 | ALERTA |
| `SLV-GEO-004` | Pontos com coordenada fora do territorio brasileiro | sinalizados, nunca removidos | 42 | ALERTA |
| `INT-EST-001` | Saidas da integracao presentes em data/silver/ | 7 | 7 | APROVADO |
| `INT-PK-001` | municipios_cliente: 1 linha por (customer_id) | 0 | 0 | APROVADO |
| `INT-PK-NUL-001` | municipios_cliente: chave (customer_id) nao nula | 0 | 0 | APROVADO |
| `INT-PK-002` | municipios_vendedor: 1 linha por (seller_id) | 0 | 0 | APROVADO |
| `INT-PK-NUL-002` | municipios_vendedor: chave (seller_id) nao nula | 0 | 0 | APROVADO |
| `INT-PK-003` | clientes_municipios: 1 linha por (customer_id) | 0 | 0 | APROVADO |
| `INT-PK-NUL-003` | clientes_municipios: chave (customer_id) nao nula | 0 | 0 | APROVADO |
| `INT-PK-004` | vendedores_municipios: 1 linha por (seller_id) | 0 | 0 | APROVADO |
| `INT-PK-NUL-004` | vendedores_municipios: chave (seller_id) nao nula | 0 | 0 | APROVADO |
| `INT-PK-005` | geografia_integrada: 1 linha por (cod_ibge) | 0 | 0 | APROVADO |
| `INT-PK-NUL-005` | geografia_integrada: chave (cod_ibge) nao nula | 0 | 0 | APROVADO |
| `INT-PK-006` | distancias_itens: 1 linha por (order_id, order_item_id) | 0 | 0 | APROVADO |
| `INT-PK-NUL-006` | distancias_itens: chave (order_id, order_item_id) nao nula | 0 | 0 | APROVADO |
| `INT-PK-007` | distancias_vendedor_cliente: 1 linha por (seller_id, customer_id) | 0 | 0 | APROVADO |
| `INT-PK-NUL-007` | distancias_vendedor_cliente: chave (seller_id, customer_id) nao nula | 0 | 0 | APROVADO |
| `INT-MET-001` | municipios_cliente.metodo_match dentro do vocabulario do contrato 5.3 | 0 | 0 | APROVADO |
| `INT-MET-003` | municipios_cliente: nao_resolvido implica cod_ibge nulo, resolvido implica preenchido | 0 | 0 | APROVADO |
| `INT-MET-005` | municipios_cliente: distancia_match_km preenchida apenas no metodo geografico | 0 | 0 | APROVADO |
| `INT-MET-007` | municipios_cliente: fallback geografico dentro de 50.0 km | 0 | 0 | APROVADO |
| `INT-FK-001` | municipios_cliente.cod_ibge existe no cadastro do IBGE | 0 | 0 | APROVADO |
| `INT-UF-001` | municipios_cliente: match respeita a UF de origem (de_para isento) | 0 | 0 | APROVADO |
| `INT-TAXA-001` | Taxa de match de clientes | documentada; nao resolvido gera alerta (plano 14.4) | 99.9135% (99355 de 99441) | ALERTA |
| `INT-MET-002` | municipios_vendedor.metodo_match dentro do vocabulario do contrato 5.3 | 0 | 0 | APROVADO |
| `INT-MET-004` | municipios_vendedor: nao_resolvido implica cod_ibge nulo, resolvido implica preenchido | 0 | 0 | APROVADO |
| `INT-MET-006` | municipios_vendedor: distancia_match_km preenchida apenas no metodo geografico | 0 | 0 | APROVADO |
| `INT-MET-008` | municipios_vendedor: fallback geografico dentro de 50.0 km | 0 | 0 | APROVADO |
| `INT-FK-002` | municipios_vendedor.cod_ibge existe no cadastro do IBGE | 0 | 0 | APROVADO |
| `INT-UF-002` | municipios_vendedor: match respeita a UF de origem (de_para isento) | 0 | 0 | APROVADO |
| `INT-TAXA-002` | Taxa de match de vendedores | documentada; nao resolvido gera alerta (plano 14.4) | 99.9354% (3093 de 3095) | ALERTA |
| `INT-DEP-001` | Correcoes de_para aplicadas tem entrada versionada com justificativa | 23 entrada(s) em de_para_municipios.csv | 29 entidade(s) corrigida(s) | APROVADO |
| `INT-DIST-001` | Nenhuma distancia negativa (plano 15) | 0 | 0 | APROVADO |
| `INT-DIST-002` | 1 linha por par (seller_id, customer_id) presente em itens_pedido | 100010 | 100010 | APROVADO |
| `INT-DIST-003` | Pares sem distancia calculada | permitido quando falta coordenada valida (plano 15) | 123 | ALERTA |
| `INT-DIST-004` | distancias_itens: flag coerente com a distancia | 0 | 0 | APROVADO |
| `INT-DIST-005` | distancias_itens preserva o grao de itens_pedido | 112650 | 112650 | APROVADO |
| `INT-DIST-006` | Itens sem distancia calculada | permitido, com motivo registrado | 555 | ALERTA |
| `INT-SOC-001` | Municipios sem populacao estimada | ausencia permanece nula (plano 14.5) | 1 | ALERTA |
| `INT-SOC-002` | Municipios sem PIB per capita | ausencia permanece nula (plano 14.5) | 1 | ALERTA |
| `INT-SOC-003` | Clientes em municipio sem indicador | informativo (plano 14.5) | 0 | APROVADO |
| `CTR-INTERFACE-001` | Onze entradas: arquivos, tipos exatos, nulidade e grao | 0 | 0 | APROVADO |
| `REP-001` | Nenhum artefato em disco de etapa cujo modulo nao existe | 0 | 0 | APROVADO |
| `REP-002` | Saidas da integracao nao sao mais antigas que as da silver | 0 | 0 | APROVADO |
| `REP-003` | de_para_municipios.csv com as colunas do contrato 5.4 | cidade_origem, uf_origem, cod_ibge, justificativa | cidade_origem, uf_origem, cod_ibge, justificativa | APROVADO |

## Casos que exigem atencao

### `SLV-NEG-006` -- ALERTA

Pedidos 'delivered' sem data real de entrega. Esperado documentado como alerta (plano 11.3), encontrado 8.

inconsistencia da origem, preservada e sinalizada por flag_entrega_ausente

### `SLV-PRD-004` -- ALERTA

Produtos com categoria 'nao_informado'. Esperado documentado (plano 16), encontrado 610.

produto sem categoria nao pode ser descartado

### `SLV-GEO-003` -- ALERTA

Prefixos de CEP sem nenhuma coordenada valida. Esperado 0 (ou documentado como alerta), encontrado 5.

19010 de 19015 prefixos agregados; nenhum ponto e inventado para os demais

### `SLV-GEO-004` -- ALERTA

Pontos com coordenada fora do territorio brasileiro. Esperado sinalizados, nunca removidos, encontrado 42.

preservados em geolocalizacao_pontos para auditoria

### `INT-TAXA-001` -- ALERTA

Taxa de match de clientes. Esperado documentada; nao resolvido gera alerta (plano 14.4), encontrado 99.9135% (99355 de 99441).

86 nao resolvido(s), listados em municipios_nao_resolvidos.csv

### `INT-TAXA-002` -- ALERTA

Taxa de match de vendedores. Esperado documentada; nao resolvido gera alerta (plano 14.4), encontrado 99.9354% (3093 de 3095).

2 nao resolvido(s), listados em municipios_nao_resolvidos.csv

### `INT-DIST-003` -- ALERTA

Pares sem distancia calculada. Esperado permitido quando falta coordenada valida (plano 15), encontrado 123.

distancia nula nunca vira zero

### `INT-DIST-006` -- ALERTA

Itens sem distancia calculada. Esperado permitido, com motivo registrado, encontrado 555.

prefixo de CEP do cliente sem coordenada valida: 302; prefixo de CEP do vendedor sem coordenada valida: 252; prefixo de CEP do vendedor e do cliente sem coordenada valida: 1

### `INT-SOC-001` -- ALERTA

Municipios sem populacao estimada. Esperado ausencia permanece nula (plano 14.5), encontrado 1.

5101837 Boa Esperança do Norte/MT

### `INT-SOC-002` -- ALERTA

Municipios sem PIB per capita. Esperado ausencia permanece nula (plano 14.5), encontrado 1.

5101837 Boa Esperança do Norte/MT
