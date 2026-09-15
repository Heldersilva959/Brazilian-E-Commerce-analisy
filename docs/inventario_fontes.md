# Inventário das fontes brutas

Descrição do que existe de fato em `data/raw/`: contagens, colunas na ordem original, tipos aparentes, vazios, encoding e separador. Levantado por inspeção direta dos arquivos, **antes** de qualquer ingestão — nenhum número aqui vem da bronze.

Responsável: membro 1. Serve de referência para os SQLs da silver, da integração e da gold, e para conferir o que o contrato assume contra o que os arquivos realmente têm.

A leitura foi feita com o módulo `csv` da biblioteca padrão, que devolve todo campo como texto e não converte nada. Isso é proposital: pandas e DuckDB aplicam inferência de tipo e de nulo, que é exatamente o que este inventário precisa medir em vez de sofrer. Os percentuais de vazio abaixo são, portanto, o estado literal do arquivo.

## 1. Resumo e conferência contra o contrato

| Arquivo | Tabela bronze | Registros | Esperado (contrato §3) | Confere |
|---|---|---|---|---|
| `olist_orders_dataset.csv` | `olist_pedidos` | 99.441 | ~99.441 | sim |
| `olist_order_items_dataset.csv` | `olist_itens_pedido` | 112.650 | ~112.650 | sim |
| `olist_products_dataset.csv` | `olist_produtos` | 32.951 | ~32.951 | sim |
| `olist_customers_dataset.csv` | `olist_clientes` | 99.441 | ~99.441 | sim |
| `olist_sellers_dataset.csv` | `olist_vendedores` | 3.095 | ~3.095 | sim |
| `olist_order_payments_dataset.csv` | `olist_pagamentos` | 103.886 | ~103.886 | sim |
| `olist_order_reviews_dataset.csv` | `olist_avaliacoes` | 99.224 | ~99.224 | sim |
| `olist_geolocation_dataset.csv` | `olist_geolocalizacao` | 1.000.163 | ~1.000.163 | sim |
| `product_category_name_translation.csv` | `olist_traducao_categoria` | 71 | 71 | sim |
| `indicadores_municipais.csv` | `socioeconomico_municipios` | 5.571 | ~5.570 | sim (+1, contrato usa `~`) |
| `municipios.json` | `ibge_municipios` | 5.571 | 5.570 | **não — +1** |

Os dez arquivos do Olist batem exatamente com o contrato. A única divergência real é o IBGE, que o contrato fixa em 5.570 sem o `~`: o cadastro atual tem 5.571 municípios. A linha a mais é **Boa Esperança do Norte (5101837, MT)**, instalada depois de 2017 — mesmo município que aparece no CSV socioeconômico com população e PIB vazios, e que no JSON não tem micro nem mesorregião. Quem dimensiona `dim_geografia` (contrato §6.2, cardinalidade 5.570) precisa decidir se ela entra.

## 2. Arquivos CSV

### `olist_orders_dataset.csv`

| Item | Valor |
|---|---|
| Caminho | `data/raw/olist/olist_orders_dataset.csv` |
| Tabela bronze de destino | `data/bronze/olist_pedidos.parquet` |
| Tamanho | 17.754.356 bytes |
| Registros (linhas de dados) | **99.441** |
| Linhas físicas do arquivo | 99.442 |
| Colunas | 8 |
| Encoding | UTF-8 sem BOM |
| Separador | vírgula `,` |
| Fim de linha | CRLF |
| Campos entre aspas | sim |
| Registros com número de campos diferente do cabeçalho | 0 |
| SHA-256 | `1dca8c9a7a8d34f0a8d0f7c272616d582e7f29d67a8c21ddd903152bf4ee6441` |

| # | Coluna | Tipo aparente | Exemplo real | Vazios | % vazio |
|---|---|---|---|---|---|
| 1 | `order_id` | texto | `e481f51cbdc54678b7cc49136f2d6af7` | 0 | 0.00% |
| 2 | `customer_id` | texto | `9ef432eb6251297304e76186b10a928d` | 0 | 0.00% |
| 3 | `order_status` | texto | `delivered` | 0 | 0.00% |
| 4 | `order_purchase_timestamp` | timestamp | `2017-10-02 10:56:33` | 0 | 0.00% |
| 5 | `order_approved_at` | timestamp | `2017-10-02 11:07:15` | 160 | 0.16% |
| 6 | `order_delivered_carrier_date` | timestamp | `2017-10-04 19:55:00` | 1.783 | 1.79% |
| 7 | `order_delivered_customer_date` | timestamp | `2017-10-10 21:25:13` | 2.965 | 2.98% |
| 8 | `order_estimated_delivery_date` | timestamp | `2017-10-18 00:00:00` | 0 | 0.00% |

Colunas de baixa cardinalidade (valores mais frequentes, com a contagem):

- `order_status`: `delivered` (96478) · `shipped` (1107) · `canceled` (625) · `unavailable` (609) · `invoiced` (314) · `processing` (301) · `created` (5) · `approved` (2)

### `olist_order_items_dataset.csv`

| Item | Valor |
|---|---|
| Caminho | `data/raw/olist/olist_order_items_dataset.csv` |
| Tabela bronze de destino | `data/bronze/olist_itens_pedido.parquet` |
| Tamanho | 15.551.322 bytes |
| Registros (linhas de dados) | **112.650** |
| Linhas físicas do arquivo | 112.651 |
| Colunas | 7 |
| Encoding | UTF-8 sem BOM |
| Separador | vírgula `,` |
| Fim de linha | CRLF |
| Campos entre aspas | sim |
| Registros com número de campos diferente do cabeçalho | 0 |
| SHA-256 | `14e321c489a729b088f26f73262b506577e2b7fcb19cf04cd70fa6276d16ff65` |

| # | Coluna | Tipo aparente | Exemplo real | Vazios | % vazio |
|---|---|---|---|---|---|
| 1 | `order_id` | texto | `00010242fe8c5a6d1ba2dd792cb16214` | 0 | 0.00% |
| 2 | `order_item_id` | inteiro | `1` | 0 | 0.00% |
| 3 | `product_id` | texto | `4244733e06e7ecb4970a6e2683c13e61` | 0 | 0.00% |
| 4 | `seller_id` | texto | `48436dade18ac8b2bce089ec2a041202` | 0 | 0.00% |
| 5 | `shipping_limit_date` | timestamp | `2017-09-19 09:45:35` | 0 | 0.00% |
| 6 | `price` | decimal | `58.90` | 0 | 0.00% |
| 7 | `freight_value` | decimal | `13.29` | 0 | 0.00% |

Colunas de baixa cardinalidade (valores mais frequentes, com a contagem):

- `order_item_id`: `1` (98666) · `2` (9803) · `3` (2287) · `4` (965) · `5` (460) · `6` (256) · `7` (58) · `8` (36)

### `olist_products_dataset.csv`

| Item | Valor |
|---|---|
| Caminho | `data/raw/olist/olist_products_dataset.csv` |
| Tabela bronze de destino | `data/bronze/olist_produtos.parquet` |
| Tamanho | 2.412.398 bytes |
| Registros (linhas de dados) | **32.951** |
| Linhas físicas do arquivo | 32.952 |
| Colunas | 9 |
| Encoding | UTF-8 sem BOM |
| Separador | vírgula `,` |
| Fim de linha | CRLF |
| Campos entre aspas | sim |
| Registros com número de campos diferente do cabeçalho | 0 |
| SHA-256 | `66f99d0261196b7f272c4ac58cf088688994a6200aa2841484defdaa42d3ade2` |

| # | Coluna | Tipo aparente | Exemplo real | Vazios | % vazio |
|---|---|---|---|---|---|
| 1 | `product_id` | texto | `1e9e8ef04dbcff4541ed26657ea517e5` | 0 | 0.00% |
| 2 | `product_category_name` | texto | `perfumaria` | 610 | 1.85% |
| 3 | `product_name_lenght` | inteiro | `40` | 610 | 1.85% |
| 4 | `product_description_lenght` | inteiro | `287` | 610 | 1.85% |
| 5 | `product_photos_qty` | inteiro | `1` | 610 | 1.85% |
| 6 | `product_weight_g` | inteiro | `225` | 2 | 0.01% |
| 7 | `product_length_cm` | inteiro | `16` | 2 | 0.01% |
| 8 | `product_height_cm` | inteiro | `10` | 2 | 0.01% |
| 9 | `product_width_cm` | inteiro | `14` | 2 | 0.01% |

Colunas de baixa cardinalidade (valores mais frequentes, com a contagem):

- `product_photos_qty`: `1` (16489) · `2` (6263) · `3` (3860) · `4` (2428) · `5` (1484) · `6` (968) · `7` (343) · `8` (192)

### `olist_customers_dataset.csv`

| Item | Valor |
|---|---|
| Caminho | `data/raw/olist/olist_customers_dataset.csv` |
| Tabela bronze de destino | `data/bronze/olist_clientes.parquet` |
| Tamanho | 9.133.399 bytes |
| Registros (linhas de dados) | **99.441** |
| Linhas físicas do arquivo | 99.442 |
| Colunas | 5 |
| Encoding | UTF-8 sem BOM |
| Separador | vírgula `,` |
| Fim de linha | CRLF |
| Campos entre aspas | sim |
| Registros com número de campos diferente do cabeçalho | 0 |
| SHA-256 | `8a80cdbd27b49a1331f70547f46b376c15cfd172cbb4bc1b74071c86acea4ec8` |

| # | Coluna | Tipo aparente | Exemplo real | Vazios | % vazio |
|---|---|---|---|---|---|
| 1 | `customer_id` | texto | `06b8999e2fba1a1fbc88172c00ba8bc7` | 0 | 0.00% |
| 2 | `customer_unique_id` | texto | `861eff4711a542e4b93843c6dd7febb0` | 0 | 0.00% |
| 3 | `customer_zip_code_prefix` | inteiro | `14409` | 0 | 0.00% |
| 4 | `customer_city` | texto | `franca` | 0 | 0.00% |
| 5 | `customer_state` | texto | `SP` | 0 | 0.00% |

Colunas de baixa cardinalidade (valores mais frequentes, com a contagem):

- `customer_state`: `SP` (41746) · `RJ` (12852) · `MG` (11635) · `RS` (5466) · `PR` (5045) · `SC` (3637) · `BA` (3380) · `DF` (2140)

### `olist_sellers_dataset.csv`

| Item | Valor |
|---|---|
| Caminho | `data/raw/olist/olist_sellers_dataset.csv` |
| Tabela bronze de destino | `data/bronze/olist_vendedores.parquet` |
| Tamanho | 177.799 bytes |
| Registros (linhas de dados) | **3.095** |
| Linhas físicas do arquivo | 3.096 |
| Colunas | 4 |
| Encoding | UTF-8 sem BOM |
| Separador | vírgula `,` |
| Fim de linha | CRLF |
| Campos entre aspas | sim |
| Registros com número de campos diferente do cabeçalho | 0 |
| SHA-256 | `c877ee451aadbec30ddc58542c12b87685703f9c8a2ba410fb3087336ac65d4a` |

| # | Coluna | Tipo aparente | Exemplo real | Vazios | % vazio |
|---|---|---|---|---|---|
| 1 | `seller_id` | texto | `3442f8959a84dea7ee197c632cb2df15` | 0 | 0.00% |
| 2 | `seller_zip_code_prefix` | inteiro | `13023` | 0 | 0.00% |
| 3 | `seller_city` | texto _(misto: texto:3094 / inteiro:1)_ | `campinas` | 0 | 0.00% |
| 4 | `seller_state` | texto | `SP` | 0 | 0.00% |

Colunas de baixa cardinalidade (valores mais frequentes, com a contagem):

- `seller_state`: `SP` (1849) · `PR` (349) · `MG` (244) · `SC` (190) · `RJ` (171) · `RS` (129) · `GO` (40) · `DF` (30)

### `olist_order_payments_dataset.csv`

| Item | Valor |
|---|---|
| Caminho | `data/raw/olist/olist_order_payments_dataset.csv` |
| Tabela bronze de destino | `data/bronze/olist_pagamentos.parquet` |
| Tamanho | 5.881.025 bytes |
| Registros (linhas de dados) | **103.886** |
| Linhas físicas do arquivo | 103.887 |
| Colunas | 5 |
| Encoding | UTF-8 sem BOM |
| Separador | vírgula `,` |
| Fim de linha | CRLF |
| Campos entre aspas | sim |
| Registros com número de campos diferente do cabeçalho | 0 |
| SHA-256 | `6ca92718f7e0ac4a77b386515ef8de1ca54cf18eb5787f07d25d0baa4e2cd870` |

| # | Coluna | Tipo aparente | Exemplo real | Vazios | % vazio |
|---|---|---|---|---|---|
| 1 | `order_id` | texto | `b81ef226f3fe1789b1e8b2acac839d17` | 0 | 0.00% |
| 2 | `payment_sequential` | inteiro | `1` | 0 | 0.00% |
| 3 | `payment_type` | texto | `credit_card` | 0 | 0.00% |
| 4 | `payment_installments` | inteiro | `8` | 0 | 0.00% |
| 5 | `payment_value` | decimal | `99.33` | 0 | 0.00% |

Colunas de baixa cardinalidade (valores mais frequentes, com a contagem):

- `payment_sequential`: `1` (99360) · `2` (3039) · `3` (581) · `4` (278) · `5` (170) · `6` (118) · `7` (82) · `8` (54)
- `payment_type`: `credit_card` (76795) · `boleto` (19784) · `voucher` (5775) · `debit_card` (1529) · `not_defined` (3)
- `payment_installments`: `1` (52546) · `2` (12413) · `3` (10461) · `4` (7098) · `10` (5328) · `5` (5239) · `8` (4268) · `6` (3920)

### `olist_order_reviews_dataset.csv`

| Item | Valor |
|---|---|
| Caminho | `data/raw/olist/olist_order_reviews_dataset.csv` |
| Tabela bronze de destino | `data/bronze/olist_avaliacoes.parquet` |
| Tamanho | 14.451.670 bytes |
| Registros (linhas de dados) | **99.224** |
| Linhas físicas do arquivo | 104.720 |
| Registros com quebra de linha dentro de um campo | **3.852** |
| Colunas | 7 |
| Encoding | UTF-8 sem BOM |
| Separador | vírgula `,` |
| Fim de linha | CRLF |
| Campos entre aspas | sim |
| Registros com número de campos diferente do cabeçalho | 0 |
| SHA-256 | `012b61c7593e34f51fa614efdf802b9c7056ce6aae5307ddb93236e7cfc797d7` |

| # | Coluna | Tipo aparente | Exemplo real | Vazios | % vazio |
|---|---|---|---|---|---|
| 1 | `review_id` | texto | `7bc2406110b926393aa56f80a40eba40` | 0 | 0.00% |
| 2 | `order_id` | texto | `73fc7af87114b39712e6da79b0a377eb` | 0 | 0.00% |
| 3 | `review_score` | inteiro | `4` | 0 | 0.00% |
| 4 | `review_comment_title` | texto _(misto: texto:11261 / inteiro:307)_ | `recomendo` | 87.656 | 88.34% |
| 5 | `review_comment_message` | texto _(misto: texto:40949 / inteiro:28)_ | `Recebi bem antes do prazo estipulado.` | 58.247 | 58.70% |
| 6 | `review_creation_date` | timestamp | `2018-01-18 00:00:00` | 0 | 0.00% |
| 7 | `review_answer_timestamp` | timestamp | `2018-01-18 21:46:59` | 0 | 0.00% |

Colunas de baixa cardinalidade (valores mais frequentes, com a contagem):

- `review_score`: `5` (57328) · `4` (19142) · `1` (11424) · `3` (8179) · `2` (3151)

### `olist_geolocation_dataset.csv`

| Item | Valor |
|---|---|
| Caminho | `data/raw/olist/olist_geolocation_dataset.csv` |
| Tabela bronze de destino | `data/bronze/olist_geolocalizacao.parquet` |
| Tamanho | 62.274.047 bytes |
| Registros (linhas de dados) | **1.000.163** |
| Linhas físicas do arquivo | 1.000.164 |
| Colunas | 5 |
| Encoding | UTF-8 sem BOM |
| Separador | vírgula `,` |
| Fim de linha | CRLF |
| Campos entre aspas | sim |
| Registros com número de campos diferente do cabeçalho | 0 |
| SHA-256 | `3b7cf4f504ce3fbb3e63693f48d20ac4a4925619720e2ed46aba2f9801260876` |

| # | Coluna | Tipo aparente | Exemplo real | Vazios | % vazio |
|---|---|---|---|---|---|
| 1 | `geolocation_zip_code_prefix` | inteiro | `01037` | 0 | 0.00% |
| 2 | `geolocation_lat` | decimal | `-23.54562128115268` | 0 | 0.00% |
| 3 | `geolocation_lng` | decimal | `-46.63929204800168` | 0 | 0.00% |
| 4 | `geolocation_city` | texto | `sao paulo` | 0 | 0.00% |
| 5 | `geolocation_state` | texto | `SP` | 0 | 0.00% |

Colunas de baixa cardinalidade (valores mais frequentes, com a contagem):

- `geolocation_state`: `SP` (404268) · `MG` (126336) · `RJ` (121169) · `RS` (61851) · `PR` (57859) · `SC` (38328) · `BA` (36045) · `GO` (20139)

### `product_category_name_translation.csv`

| Item | Valor |
|---|---|
| Caminho | `data/raw/olist/product_category_name_translation.csv` |
| Tabela bronze de destino | `data/bronze/olist_traducao_categoria.parquet` |
| Tamanho | 2.613 bytes |
| Registros (linhas de dados) | **71** |
| Linhas físicas do arquivo | 72 |
| Colunas | 2 |
| Encoding | UTF-8 com BOM |
| Separador | vírgula `,` |
| Fim de linha | CRLF |
| Campos entre aspas | não |
| Registros com número de campos diferente do cabeçalho | 0 |
| SHA-256 | `a81f0d1f27b27e7293f761bc79e3ce8f348ee39c4b3ed3e49bde38f478586278` |

| # | Coluna | Tipo aparente | Exemplo real | Vazios | % vazio |
|---|---|---|---|---|---|
| 1 | `product_category_name` | texto | `beleza_saude` | 0 | 0.00% |
| 2 | `product_category_name_english` | texto | `health_beauty` | 0 | 0.00% |

### `indicadores_municipais.csv`

| Item | Valor |
|---|---|
| Caminho | `data/raw/socioeconomico/indicadores_municipais.csv` |
| Tabela bronze de destino | `data/bronze/socioeconomico_municipios.parquet` |
| Tamanho | 158.003 bytes |
| Registros (linhas de dados) | **5.571** |
| Linhas físicas do arquivo | 5.572 |
| Colunas | 4 |
| Encoding | UTF-8 sem BOM |
| Separador | vírgula `,` |
| Fim de linha | CRLF |
| Campos entre aspas | não |
| Registros com número de campos diferente do cabeçalho | 0 |
| SHA-256 | `b9fb5058751d8499748ab38e4004ec66720f0ffced3f68206a6e7d78f232599b` |

| # | Coluna | Tipo aparente | Exemplo real | Vazios | % vazio |
|---|---|---|---|---|---|
| 1 | `cod_ibge` | inteiro | `1100015` | 0 | 0.00% |
| 2 | `ano_referencia` | inteiro | `2017` | 0 | 0.00% |
| 3 | `populacao_estimada` | inteiro | `25437` | 1 | 0.02% |
| 4 | `pib_per_capita` | decimal | `19081.42` | 1 | 0.02% |

Colunas de baixa cardinalidade (valores mais frequentes, com a contagem):

- `ano_referencia`: `2017` (5571)

## 3. IBGE Localidades — `data/raw/ibge/municipios.json`

| Item | Valor |
|---|---|
| Caminho | `data/raw/ibge/municipios.json` |
| Tabela bronze de destino | `data/bronze/ibge_municipios.parquet` |
| Tamanho | 2.470.036 bytes |
| Registros (municípios) | **5.571** |
| Estrutura | lista JSON de objetos, um por município |
| Encoding | UTF-8 sem BOM, uma única linha física |
| SHA-256 | `86ecdccdf97d72e7e5e46f0854cfcea8bacc28154cc1bc4ed0e6110e3a6c9c02` |

### 3.1 Todos os caminhos aninhados

`vezes` é em quantos dos 5.571 municípios o caminho aparece; `nulos` em quantos ele aparece com valor `null`.

| Caminho | Tipo | Exemplo | Vezes | Nulos |
|---|---|---|---|---|
| `id` | int:5.571 | `1100015` | 5.571 | 0 |
| `microrregiao` | objeto:5.570 / null:1 | — | 5.571 | 1 |
| `microrregiao.id` | int:5.570 | `11006` | 5.570 | 0 |
| `microrregiao.mesorregiao` | objeto:5.570 | — | 5.570 | 0 |
| `microrregiao.mesorregiao.UF` | objeto:5.570 | — | 5.570 | 0 |
| `microrregiao.mesorregiao.UF.id` | int:5.570 | `11` | 5.570 | 0 |
| `microrregiao.mesorregiao.UF.nome` | str:5.570 | `Rondônia` | 5.570 | 0 |
| `microrregiao.mesorregiao.UF.regiao` | objeto:5.570 | — | 5.570 | 0 |
| `microrregiao.mesorregiao.UF.regiao.id` | int:5.570 | `1` | 5.570 | 0 |
| `microrregiao.mesorregiao.UF.regiao.nome` | str:5.570 | `Norte` | 5.570 | 0 |
| `microrregiao.mesorregiao.UF.regiao.sigla` | str:5.570 | `N` | 5.570 | 0 |
| `microrregiao.mesorregiao.UF.sigla` | str:5.570 | `RO` | 5.570 | 0 |
| `microrregiao.mesorregiao.id` | int:5.570 | `1102` | 5.570 | 0 |
| `microrregiao.mesorregiao.nome` | str:5.570 | `Leste Rondoniense` | 5.570 | 0 |
| `microrregiao.nome` | str:5.570 | `Cacoal` | 5.570 | 0 |
| `nome` | str:5.571 | `Alta Floresta D'Oeste` | 5.571 | 0 |
| `regiao-imediata` | objeto:5.571 | — | 5.571 | 0 |
| `regiao-imediata.id` | int:5.571 | `110005` | 5.571 | 0 |
| `regiao-imediata.nome` | str:5.571 | `Cacoal` | 5.571 | 0 |
| `regiao-imediata.regiao-intermediaria` | objeto:5.571 | — | 5.571 | 0 |
| `regiao-imediata.regiao-intermediaria.UF` | objeto:5.571 | — | 5.571 | 0 |
| `regiao-imediata.regiao-intermediaria.UF.id` | int:5.571 | `11` | 5.571 | 0 |
| `regiao-imediata.regiao-intermediaria.UF.nome` | str:5.571 | `Rondônia` | 5.571 | 0 |
| `regiao-imediata.regiao-intermediaria.UF.regiao` | objeto:5.571 | — | 5.571 | 0 |
| `regiao-imediata.regiao-intermediaria.UF.regiao.id` | int:5.571 | `1` | 5.571 | 0 |
| `regiao-imediata.regiao-intermediaria.UF.regiao.nome` | str:5.571 | `Norte` | 5.571 | 0 |
| `regiao-imediata.regiao-intermediaria.UF.regiao.sigla` | str:5.571 | `N` | 5.571 | 0 |
| `regiao-imediata.regiao-intermediaria.UF.sigla` | str:5.571 | `RO` | 5.571 | 0 |
| `regiao-imediata.regiao-intermediaria.id` | int:5.571 | `1102` | 5.571 | 0 |
| `regiao-imediata.regiao-intermediaria.nome` | str:5.571 | `Ji-Paraná` | 5.571 | 0 |

### 3.2 Campos que a integração geográfica precisa (seção 4.9 do contrato)

| Campo no contrato | Caminho no JSON | Observação |
|---|---|---|
| `cod_ibge` | `id` | inteiro de 7 dígitos no JSON; a bronze grava como texto |
| `municipio` | `nome` | nome oficial, acentuado |
| `uf` | `microrregiao.mesorregiao.UF.sigla` | **ou** `regiao-imediata.regiao-intermediaria.UF.sigla` |
| `regiao` | `microrregiao.mesorregiao.UF.regiao.nome` | **ou** o mesmo ramo por `regiao-imediata` |
| `mesorregiao` | `microrregiao.mesorregiao.nome` | ausente em 1 município |
| `microrregiao` | `microrregiao.nome` | ausente em 1 município |

O ramo `regiao-imediata` está preenchido nos 5.571 municípios; o ramo `microrregiao` não. Para UF e região, ler pelo ramo `regiao-imediata` evita o caso nulo.

Primeiro registro do arquivo, na íntegra:

```json
{
  "id": 1100015,
  "nome": "Alta Floresta D'Oeste",
  "microrregiao": {
    "id": 11006,
    "nome": "Cacoal",
    "mesorregiao": {
      "id": 1102,
      "nome": "Leste Rondoniense",
      "UF": {
        "id": 11,
        "sigla": "RO",
        "nome": "Rondônia",
        "regiao": {
          "id": 1,
          "sigla": "N",
          "nome": "Norte"
        }
      }
    }
  },
  "regiao-imediata": {
    "id": 110005,
    "nome": "Cacoal",
    "regiao-intermediaria": {
      "id": 1102,
      "nome": "Ji-Paraná",
      "UF": {
        "id": 11,
        "sigla": "RO",
        "nome": "Rondônia",
        "regiao": {
          "id": 1,
          "sigla": "N",
          "nome": "Norte"
        }
      }
    }
  }
}
```

## 4. Originais do SIDRA (não entram na bronze)

Ficam em `data/raw/socioeconomico/originais/` para auditoria. O contrato lista onze tabelas bronze e nenhuma delas é o JSON do SIDRA: a entrada consumida é o CSV consolidado `indicadores_municipais.csv` (seção 2 deste documento).

| Arquivo | Registros | Bytes | SHA-256 |
|---|---|---|---|
| `sidra_6579_populacao_estimada_2017.json` | 5.572 | 1.508.646 | `0afa9c65290fc18a…` |
| `sidra_5938_pib_2017.json` | 5.571 | 1.576.397 | `f0fccc3b2c481df1…` |

Os dois arquivos têm o formato do `apisidra`: uma lista de objetos de chaves curtas, em que o **primeiro elemento traz os rótulos das colunas, não dados** — por isso a contagem de elementos é 5.572 e 5.571, e não 5.571 e 5.570.

```json
{
  "NC": "Nível Territorial (Código)",
  "NN": "Nível Territorial",
  "MC": "Unidade de Medida (Código)",
  "MN": "Unidade de Medida",
  "V": "Valor",
  "D1C": "Município (Código)",
  "D1N": "Município",
  "D2C": "Variável (Código)",
  "D2N": "Variável",
  "D3C": "Ano (Código)",
  "D3N": "Ano"
}
```

```json
{
  "NC": "6",
  "NN": "Município",
  "MC": "45",
  "MN": "Pessoas",
  "V": "25437",
  "D1C": "1100015",
  "D1N": "Alta Floresta D'Oeste - RO",
  "D2C": "9324",
  "D2N": "População residente estimada",
  "D3C": "2017",
  "D3N": "2017"
}
```

## 5. Armadilhas de leitura medidas nestes arquivos

A seção 2 do contrato manda preservar a string vazia como `''` na bronze e deixar a conversão para `NULL` na silver. Os quatro pontos abaixo foram verificados nestes arquivos, não deduzidos da documentação das bibliotecas.

**1. O pandas transforma campo vazio em `NaN`, mesmo com `dtype=str`.** Medido em `olist_products_dataset.csv`, coluna `product_category_name`:

| Leitura | `NaN` | `''` |
|---|---|---|
| `read_csv(dtype=str)` | 610 | 0 |
| `read_csv(dtype=str, keep_default_na=False)` | 0 | 610 |

Vale igual para campo vazio **entre aspas**: `orders.order_delivered_customer_date` tem 2.965 campos `""`, todos viram `NaN` na leitura padrão. Sem `keep_default_na=False` a bronze quebraria a seção 2 do contrato em todas as tabelas.

**2. `product_category_name_translation.csv` começa com BOM.** Lido com `encoding='utf-8'` pelo módulo `csv`, a primeira coluna passa a se chamar `\ufeffproduct_category_name` e o join da silver §4.3 falha sem erro. Com `encoding='utf-8-sig'` o nome sai limpo. O pandas remove o BOM sozinho; o módulo `csv` não.

**3. `olist_order_reviews_dataset.csv` tem 3.852 registros com quebra de linha dentro do campo de comentário.** São 104.720 linhas físicas para 99.224 registros. Por isso `_linha_origem` é o número do **registro**, base 1 sem contar o cabeçalho: é o único valor reproduzível e o que casa com a contagem do contrato.

**4. Nenhum CSV contém os literais `NA`, `null`, `nan` ou `None` como valor de verdade.** Varredura feita em todas as colunas dos onze arquivos. Ou seja, `keep_default_na=False` não corre o risco de preservar um texto que na origem significava ausência.

Consequência para a bronze: leitura com `csv`/pandas em modo totalmente textual, `keep_default_na=False`, `dtype=str`, `encoding='utf-8-sig'` (inofensivo nos arquivos sem BOM) e `_linha_origem` contado por registro.

## 6. Observações para as outras camadas

- **`indicadores_municipais.csv` chama a coluna de `populacao_estimada`**, enquanto a seção 4.9 do contrato nomeia `populacao` na silver. A bronze preserva o nome de origem; o renomear é da silver.
- **O código do IBGE é inteiro no JSON e texto no CSV.** Na bronze os dois viram texto de 7 posições. O join da silver §4.9 é por código, e comparar `int` com `str` devolve zero linhas sem erro.
- **Prefixos de CEP já vêm com 5 posições e zero à esquerda** nos três arquivos que os têm: 1.027 vendedores e 245.733 linhas de geolocalização começam com `0`. Ler a coluna como número apaga esse zero e quebra o join de §4.8. A bronze entrega o texto como está.
- **`microrregiao` e `mesorregiao` são nulos em Boa Esperança do Norte.** Código que assume esses ramos sempre presentes quebra nesse registro.
- **`order_status` tem 8 valores distintos e `payment_type` tem 5**, incluindo o `not_defined` que a §4.6 manda tratar como `nao_informado`. As listas completas estão nas tabelas da seção 2.

## 7. Amostra da sujeira que a silver e a integração vão encontrar

A bronze não corrige nada disto — está aqui porque é o que define o trabalho das camadas seguintes, e porque serve de prova de que a ingestão preservou o valor original.

**Nome de cidade.** As três colunas de cidade têm convenções diferentes:

| | `geolocation_city` | `customer_city` | `seller_city` |
|---|---|---|---|
| Valores distintos | 8.011 | 4.119 | 611 |
| Com acento | 2.081 | 0 | 0 |
| Com UF ou país embutido (`/` ou `,`) | 2 | 0 | 17 |
| Com dígito | 8 | 1 | 1 |
| Com espaço nas pontas | 1 | 0 | 0 |

Ou seja: `geolocation_city` é acentuado e as outras duas não. Comparar as três sem passar por `normalizar_texto` (§5.1) não casa nada. Exemplos reais, copiados do arquivo:

- Acentuados só na geolocalização: `são paulo`, `jundiaí`, `taboão da serra`, `carapicuíba`
- Sem o espaço: `sãopaulo`
- Escape de URL não desfeito na origem: `lambari d%26apos%3boeste`, `são joão do pau d%26apos%3balho` (é `d'oeste` e `d'alho`)
- Reticências no começo: `...arraial do cabo`
- Espaço no fim: `salvador ` (com o espaço)
- UF ou país no mesmo campo: `auriflama/sp`, `sp / sp`, `sbc/sp`, `novo hamburgo, rio grande do sul, brasil`
- Um CEP no lugar do nome: `04482255` em `seller_city`
- Ordinal escrito de duas formas: `4o. centenario` e `4º centenario`

Confirmado que os acentos são UTF-8 íntegro, não mojibake: `são paulo` são os pontos de código corretos. Se aparecer `s?o paulo` na sua tela, é o console do Windows, não o arquivo.

**Coordenadas.** `geolocation_lat` vai de -36,606 a 45,066 e `geolocation_lng` de -101,467 a 121,105 — há ponto caindo na Ásia. Dentro do retângulo que a §4.8 manda usar (`lat ∈ [-34, 6]`, `lng ∈ [-74, -34]`), sobram todos menos **42 linhas**. É esse o número que a silver deve registrar no log ao descartar.

**Datas e valores continuam texto na bronze.** `order_purchase_timestamp` é `2017-10-02 10:56:33` como string, `price` é `58.90` como string com ponto decimal. Nenhum deles é convertido aqui — a tipagem é da silver, conforme §4.

