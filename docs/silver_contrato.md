# Contrato da camada Silver — Membro 2

Documentação própria do responsável pela Silver, para revisão do grupo em
`docs/contratos_dados.md`. Escrita antes da bronze existir, a partir dos
cabeçalhos e valores reais dos nove CSVs em `data/raw/olist/` (inspecionados
diretamente com DuckDB) — nenhum dado fictício foi criado para antecipar a
etapa.

`src/silver/transform.py` implementa o que está aqui. Como a bronze
(responsabilidade do Membro 1) ainda não existe, o módulo não pôde ser
executado contra `data/bronze/*.parquet` de verdade; a lógica SQL foi validada
à parte, lendo os CSVs reais diretamente (script de uso único, não
versionado), simulando apenas o formato colunar da bronze (colunas originais
como string). Os resultados dessa validação estão na seção 8.

## 1. Contrato de entrada esperado da bronze

Nomes de arquivo **a confirmar com o Membro 1** — usei nomes em português para
manter a mesma convenção da silver; se a bronze nomear diferente, é só ajustar
o dicionário `BRONZE_ESPERADA` em `transform.py`, sem tocar no resto do código.

| Arquivo esperado | Fonte Olist | Colunas originais (todas string, conforme contrato da bronze) |
| --- | --- | --- |
| `data/bronze/pedidos.parquet` | `olist_orders_dataset.csv` | `order_id, customer_id, order_status, order_purchase_timestamp, order_approved_at, order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date` |
| `data/bronze/itens_pedido.parquet` | `olist_order_items_dataset.csv` | `order_id, order_item_id, product_id, seller_id, shipping_limit_date, price, freight_value` |
| `data/bronze/pagamentos.parquet` | `olist_order_payments_dataset.csv` | `order_id, payment_sequential, payment_type, payment_installments, payment_value` |
| `data/bronze/avaliacoes.parquet` | `olist_order_reviews_dataset.csv` | `review_id, order_id, review_score, review_comment_title, review_comment_message, review_creation_date, review_answer_timestamp` |
| `data/bronze/produtos.parquet` | `olist_products_dataset.csv` | `product_id, product_category_name, product_name_lenght, product_description_lenght, product_photos_qty, product_weight_g, product_length_cm, product_height_cm, product_width_cm` |
| `data/bronze/clientes.parquet` | `olist_customers_dataset.csv` | `customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state` |
| `data/bronze/vendedores.parquet` | `olist_sellers_dataset.csv` | `seller_id, seller_zip_code_prefix, seller_city, seller_state` |
| `data/bronze/geolocalizacao.parquet` | `olist_geolocation_dataset.csv` | `geolocation_zip_code_prefix, geolocation_lat, geolocation_lng, geolocation_city, geolocation_state` |
| `data/bronze/traducao_categorias.parquet` | `product_category_name_translation.csv` | `product_category_name, product_category_name_english` |

Todas as colunas de origem chegam como string, mais `_fonte`, `_arquivo_origem`
e `_data_ingestao` (contrato da bronze no README). A silver faz toda a
tipagem: datas, decimais e inteiros são convertidos aqui, nunca antes.

Todo prefixo de CEP (`*_zip_code_prefix`) tem 5 dígitos nos três arquivos
(clientes, vendedores, geolocalização) — confirmado nos dados reais — e deve
permanecer string para preservar zeros à esquerda.

## 2. Tabelas produzidas e grão

| Arquivo | Grão | PK |
| --- | --- | --- |
| `data/silver/pedidos.parquet` | um pedido | `order_id` |
| `data/silver/itens_pedido.parquet` | um item de pedido | `order_id + item_pedido_id` |
| `data/silver/pagamentos.parquet` | pagamentos agregados de um pedido | `order_id` |
| `data/silver/avaliacoes.parquet` | uma avaliação por pedido (deduplicada) | `order_id` |
| `data/silver/produtos.parquet` | um produto | `product_id` |
| `data/silver/clientes.parquet` | um `customer_id` (não o unique_id) | `customer_id` |
| `data/silver/vendedores.parquet` | um vendedor | `seller_id` |
| `data/silver/geolocalizacao_pontos.parquet` | um ponto bruto de geolocalização, com flag de validade | grão do arquivo original (sem PK) |
| `data/silver/geolocalizacao_cep.parquet` | um prefixo de CEP | `cep_prefixo` |

Nenhuma tabela silver junta pedidos com itens, pagamentos ou avaliações — isso
é responsabilidade da gold, para não multiplicar linhas antes da hora.

## 3. `pedidos`

Renomeações e tipos: `order_id`→string, `customer_id`→string,
`status_pedido`→string, `ts_compra/ts_aprovacao/ts_envio_transportadora/
ts_entrega_cliente/ts_estimativa_entrega`→`TIMESTAMP`.

Regras (dados reais de `olist_orders_dataset.csv`, 99.441 linhas):

- **Entrega ausente:** `ts_entrega_cliente` nulo vira `flag_entrega_ausente =
  true`, sem inventar data. Achado real: **8 pedidos com `status_pedido =
  'delivered'` têm `ts_entrega_cliente` nulo** — inconsistência conhecida do
  dataset Olist, preservada e sinalizada, não corrigida.
- `dias_ate_entrega = date_diff('day', ts_compra, ts_entrega_cliente)` **somente**
  quando `status_pedido = 'delivered'` e `ts_entrega_cliente` não é nulo; caso
  contrário fica `NULL` (nunca zero).
- `dias_atraso = date_diff('day', ts_estimativa_entrega, ts_entrega_cliente)`,
  mesma condição de elegibilidade. Pode ser negativo (entrega antes do
  previsto) — intervalo real observado: -147 a +188 dias.
- `flag_atraso = dias_atraso > 0` **apenas quando `dias_atraso` não é nulo**;
  quando não há prazo elegível, `flag_atraso` fica `NULL`, nunca `false`. Isso
  segue a regra do README: ausência de prazo não é zero atraso.
- `ano_mes_compra = strftime(ts_compra, '%Y-%m')`.

## 4. `itens_pedido`

Renomeia `order_item_id`→`item_pedido_id`, `price`→`preco_produto`,
`freight_value`→`valor_frete`, ambos `DECIMAL(12,2)`.
`valor_total_item = preco_produto + valor_frete` (regra do README: total do
item é preço + frete, sem repetir valores de pagamento neste grão).

**Faixa de preço** (baseada nos quartis reais de `price`, 112.650 itens):

| Faixa | Intervalo |
| --- | --- |
| `baixo` | `preco_produto <= 39.90` (≈ Q1) |
| `medio_baixo` | `39.90 < preco_produto <= 74.99` (≈ mediana) |
| `medio_alto` | `74.99 < preco_produto <= 134.90` (≈ Q3) |
| `alto` | `preco_produto > 134.90` |

**Outlier de frete:** `flag_frete_outlier = valor_frete > (Q3 + 1.5 * IQR)`,
Tukey clássico, calculado **dinamicamente por SQL** sobre o próprio conjunto
(não hardcoded), para não precisar recalcular à mão se os dados mudarem. Nos
dados reais isso dá uma cerca de ≈ R$ 33,26 (Q1=13,08, Q3=21,15) e sinaliza
11.613 dos 112.650 itens (≈10,3%) — proporção alta porque o Brasil é
continental e frete cresce com distância; é sinalização para análise, não
remoção (sem winsorização, conforme README). 383 itens têm frete R$ 0,00,
preservados sem flag de erro (o dataset não distingue frete grátis de dado
ausente).

## 5. `pagamentos` (agregado por pedido)

Agrega `olist_order_payments_dataset.csv` (103.886 linhas de pagamento) antes
de qualquer join, como o README exige.

- `valor_total_pago = sum(payment_value)` por `order_id`.
- `tipo_pagamento_predominante`: o `payment_type` com maior soma de
  `payment_value` agregada nesse pedido.
- `parcelas_tipo_predominante`: o maior `payment_installments` observado
  dentro desse tipo predominante, para aquele pedido.
- `qtd_transacoes`, `qtd_metodos_distintos` (contagem de `payment_type`
  distintos usados no pedido — 2.246 dos 99.440 pedidos usam mais de um
  método).
- **Empate:** não há nenhum caso real de empate no valor agregado por tipo
  (conferido nos dados). Regra estável documentada para quando ocorrer:
  desempatar por ordem alfabética ascendente de `payment_type`
  (`boleto` < `credit_card` < `debit_card` < `not_defined` < `voucher`).

## 6. `avaliacoes` (uma por pedido)

`olist_order_reviews_dataset.csv` tem 98.673 `order_id` distintos e **547
pedidos com mais de uma avaliação** (até 3). Regra de desempate, na ordem:

1. Maior `review_creation_date` (mais recente vence).
2. Empate nessa data (157 pares reais): maior `review_answer_timestamp`.
3. Nos dados reais não há empate simultâneo nas duas colunas (conferido), mas
   por determinismo total o critério final é `review_id` em ordem decrescente.

Demais avaliações do mesmo pedido não entram na silver (ficam preservadas na
bronze, responsabilidade do Membro 1). Campo `flag_avaliacao_duplicada_pedido`
marca os 547 pedidos onde havia mais de uma avaliação na origem, para
transparência na gold/qualidade.

`review_score`→`nota_review INTEGER` (valores reais: 1 a 5, sem nulos).

## 7. `produtos`

`olist_products_dataset.csv`, 32.951 produtos.

- **Categoria ausente:** `categoria_produto = coalesce(product_category_name,
  'nao_informado')` — 610 produtos reais sem categoria, preservados com seus
  itens/vendas, conforme README.
- **Tradução:** join com `traducao_categorias`. Achado real: **2 categorias
  existentes não têm tradução no arquivo oficial** (`pc_gamer` e
  `portateis_cozinha_e_preparadores_de_alimentos`). Regra: quando a tradução
  não existe, `categoria_produto_ingles` recebe a própria categoria em
  português (nunca `nao_informado` para um produto que tem categoria), e
  `flag_categoria_sem_traducao = true` sinaliza o caso para quem for usar essa
  coluna.
- **Peso e dimensões ausentes:** mediana por `categoria_produto` (a categoria
  original em português, antes da tradução). Nos dados reais só **2 produtos**
  têm peso/dimensões nulos, e a categoria de ambos tem outros produtos com
  valor — a imputação por mediana de categoria cobre os dois casos; o galho de
  "categoria sem valores suficientes" (mínimo de 5 observações não nulas,
  documentado aqui) mantém nulo e loga a ocorrência, mas não é exercitado
  pelos dados atuais. `flag_peso_imputado` e `flag_dimensoes_imputadas`
  marcam as linhas alteradas.

## 8. `clientes` e `vendedores`

Passagem limpa de `olist_customers_dataset.csv` (99.441 linhas) e
`olist_sellers_dataset.csv` (3.095 linhas): `trim` em cidade/UF, prefixo de
CEP mantido como string de 5 dígitos. **Nenhuma normalização de nome de
cidade (NFKD/acentos/pontuação) acontece aqui** — isso é do Membro 3
(`src/utils/normalizacao.py`), para não duplicar a lógica de match em dois
lugares. A silver entrega texto limpo (sem espaços supérfluos), não
normalizado para chave de match.

## 9. Geolocalização — o entregável para o Membro 3

`olist_geolocation_dataset.csv` tem 1.000.163 pontos brutos e 19.015 prefixos
de CEP distintos.

- **`geolocalizacao_pontos`:** os pontos de origem com
  `flag_coordenada_invalida` — verdadeiro quando lat/lng caem fora de uma
  caixa delimitadora aproximada do Brasil (`lat NOT BETWEEN -34 AND 6` ou
  `lng NOT BETWEEN -75 AND -33`). Nos dados reais isso pega 31 latitudes e 37
  longitudes fora da caixa (alguns pontos claramente errados, ex.: coordenadas
  no hemisfério norte). Nenhum registro é removido aqui — ele fica, com a
  flag, para auditoria (conforme README).
- **`geolocalizacao_cep`:** mediana de `geolocation_lat`/`geolocation_lng`
  por `cep_prefixo`, **usando apenas os pontos com
  `flag_coordenada_invalida = false`**. Essa é a tabela que o Membro 3 usa
  como insumo do fallback geográfico (mediana por prefixo de CEP → Haversine
  por UF), conforme a ordem definida no README. Resultado real: **19.010** dos
  19.015 prefixos têm ao menos um ponto válido e entram na tabela; **5
  prefixos ficam de fora** por terem só coordenadas inválidas — não é
  inventado ponto nenhum para eles, o que é coerente com a regra do Membro 3
  de não estimar ponto sem evidência.

## 10. Validação da lógica (sem bronze pronta)

Como não crio dados fictícios para antecipar a etapa, rodei o próprio
`src/silver/transform.py` (mesmo código, sem alterar nenhuma regra) contra uma
bronze simulada: os nove CSVs reais convertidos para string coluna a coluna
(`all_varchar=true`), do jeito que a bronze contratualmente vai entregar,
gravados em parquet fora do repositório (scratchpad, não commitado). Todas as
nove tabelas foram geradas e conferidas linha a linha contra os números
levantados nas seções acima:

- `pedidos`: 99.441 linhas; exatamente 8 com `flag_entrega_ausente = true`
  (todas com `status_pedido = 'delivered'`); nenhuma linha com
  `dias_atraso`/`flag_atraso` inconsistente entre si; atraso real entre -147 e
  +188 dias.
- `itens_pedido`: 112.650 linhas; `valor_total_item` bate com
  `preco_produto + valor_frete` em 100% das linhas; `flag_frete_outlier`
  marca exatamente 11.613 linhas; `faixa_preco` distribui as 112.650 linhas em
  quatro grupos de tamanho parecido (27.940 a 28.501 cada), como esperado de
  cortes por quartil.
- `pagamentos`: 99.440 pedidos agregados; `sum(valor_total_pago)` bate, no
  centavo, com a soma de `payment_value` no CSV original
  (R$ 16.008.872,12); sem empate real no tipo predominante.
- `avaliacoes`: 98.673 pedidos; nos dois pedidos com empate de data
  inspecionados manualmente (`0035246a40f520710769010f752e7507` e
  `0176a6846bcb3b0d3aa3116a9a768597`), o desempate escolheu a avaliação
  correta (maior `review_creation_date`, depois maior
  `review_answer_timestamp`); 547 pedidos marcados com
  `flag_avaliacao_duplicada_pedido`.
- `produtos`: 32.951 linhas; 610 com `categoria_produto = 'nao_informado'`;
  as 13 linhas das 2 categorias sem tradução oficial (`pc_gamer` e
  `portateis_cozinha_e_preparadores_de_alimentos`) ficam com
  `flag_categoria_sem_traducao = true`; exatamente 2 linhas com
  `flag_peso_imputado`/`flag_dimensoes_imputadas`, e nenhuma linha final com
  peso ou dimensão nula.
- `geolocalizacao_cep`: 19.010 prefixos agregados a partir de 1.000.163
  pontos brutos; 26 pontos sinalizados como inválidos (fora da caixa do
  Brasil) e excluídos do cálculo da mediana.

Isso não substitui a integração real com a bronze do Membro 1 — é a garantia
de que a lógica em si está correta antes dela existir.

Quando a bronze existir, basta apontar `BRONZE_ESPERADA` em
`src/silver/transform.py` para os arquivos reais e rodar
`python -m src.silver.transform` — o script falha cedo, citando nome e
caminho, se algum arquivo obrigatório da bronze estiver ausente.

## 11. Pendências que dependem de decisão conjunta / de outros membros

- Confirmar com o Membro 1 os nomes reais dos arquivos parquet da bronze
  (seção 1) e ajustar `BRONZE_ESPERADA` se forem diferentes dos que assumi.
- `distancia_km` (vendedor–cliente) depende do ponto representativo municipal
  que o Membro 3 só calcula depois de receber `geolocalizacao_cep` — por isso
  não está nesta camada; fica para a integração/gold.
- Limiar de "porte municipal" é do Membro 3/4, não tratado aqui.
- O limite mínimo de 5 observações para a mediana de categoria de produto é
  uma escolha minha, sujeita a revisão do grupo na reunião de alinhamento.
