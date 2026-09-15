# Contrato de dados — DW E-commerce Brasileiro

**Versão:** 1.1
**Status:** rascunho para aprovação na reunião de alinhamento
**Consolidação:** membro 1 · **Aprovação:** todos os membros

Este documento é a fonte única de verdade sobre nomes, grãos, tipos, caminhos e regras de negócio das tabelas intermediárias. Nenhuma implementação começa antes da aprovação. Alterações seguem o processo da seção 9.

---

## 1. Convenções gerais

| Assunto | Regra |
|---|---|
| Idioma | Tabelas, colunas e comentários em português, sem acento nos identificadores |
| Nomenclatura | `snake_case`; dimensões com prefixo `dim_`, fatos com `fato_` |
| Formato bronze/silver | Parquet, compressão snappy, um arquivo por tabela |
| Formato gold | DuckDB em `data/gold/dw.duckdb` |
| Valores monetários | `DECIMAL(12,2)` a partir da silver — nunca `FLOAT` |
| Distâncias | `DECIMAL(10,2)`, em quilômetros |
| Datas e horas | `TIMESTAMP` (sem fuso); datas puras como `DATE` |
| Booleanos | `BOOLEAN` nativo na silver; `SMALLINT` (0/1) nas medidas da fato |
| Codificação de texto | UTF-8 em todos os arquivos |
| No Git | `data/raw/` — as fontes vão versionadas junto com o código (ver abaixo) |
| Fora do Git | `data/bronze/`, `data/silver/`, `data/gold/`, `*.parquet`, `*.duckdb`, `.venv/` |

**Por que `data/raw/` vai para o repositório.** O download do Olist é manual e exige conta no Kaggle, e as consultas ao SIDRA dependem de a API estar no ar. Versionar as fontes é o que garante que os quatro membros — e quem for corrigir o trabalho — executem o pipeline sobre exatamente os mesmos bytes. São cerca de 120 MB, dentro do que o GitHub aceita sem LFS, e os arquivos não mudam ao longo do projeto.

As saídas das três camadas ficam fora: são derivadas de `data/raw/`, reconstruídas por inteiro a cada execução, e commitá-las produziria conflito binário toda vez que alguém rodasse o pipeline. O mesmo vale para `data/bronze/_manifesto.json`, que é estado local de ingestão.

---

## 2. Representação de nulos e membros técnicos

Distinguimos três situações. Confundi-las é o erro mais comum e custa nota no critério de tratamento de valores nulos.

**Nulo legítimo** — a ausência é informação de negócio. Exemplo: `data_entrega_cliente` de um pedido cancelado. Mantém-se `NULL` em todas as camadas. Nunca imputar, nunca descartar a linha.

**Nulo por falha de cadastro** — o dado deveria existir. Exemplo: `categoria_produto` ausente em ~610 produtos. Na silver vira o literal `'nao_informado'` (texto) ou a mediana da categoria (numérico, com flag `flag_imputado = TRUE`).

**Membro técnico nas dimensões** — toda dimensão tem uma linha com `sk = -1`, usada quando a fato não consegue resolver a FK. Atributos textuais recebem `'NAO INFORMADO'`, numéricos recebem `NULL`. Isso garante zero órfãos sem inventar dado.

Na bronze, strings vazias (`''`) são preservadas como estão. A conversão de `''` para `NULL` acontece exclusivamente na silver.

---

## 3. Camada bronze — responsável: membro 1

Leitura sem qualquer limpeza. **Todas as colunas são `VARCHAR`**, inclusive datas e valores. Nenhum filtro, nenhuma deduplicação, nenhum cast.

### Colunas de linhagem (obrigatórias em todas as tabelas)

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `_fonte` | VARCHAR | `olist`, `ibge_api`, `sidra` |
| `_arquivo_origem` | VARCHAR | Nome do arquivo ou endpoint |
| `_data_ingestao` | TIMESTAMP | Momento da execução da bronze |
| `_linha_origem` | BIGINT | Número da linha no arquivo original, base 1 |

`_data_ingestao` só é atualizada quando o arquivo de origem muda (comparação por hash). Reexecução com fonte inalterada preserva o valor anterior.

### Tabelas

| Arquivo de saída | Origem | Grão | Linhas esperadas |
|---|---|---|---|
| `data/bronze/olist_pedidos.parquet` | `olist_orders_dataset.csv` | 1 por pedido | ~99.441 |
| `data/bronze/olist_itens_pedido.parquet` | `olist_order_items_dataset.csv` | 1 por item | ~112.650 |
| `data/bronze/olist_produtos.parquet` | `olist_products_dataset.csv` | 1 por produto | ~32.951 |
| `data/bronze/olist_clientes.parquet` | `olist_customers_dataset.csv` | 1 por `customer_id` | ~99.441 |
| `data/bronze/olist_vendedores.parquet` | `olist_sellers_dataset.csv` | 1 por vendedor | ~3.095 |
| `data/bronze/olist_pagamentos.parquet` | `olist_order_payments_dataset.csv` | 1 por parcela de pagamento | ~103.886 |
| `data/bronze/olist_avaliacoes.parquet` | `olist_order_reviews_dataset.csv` | 1 por avaliação | ~99.224 |
| `data/bronze/olist_geolocalizacao.parquet` | `olist_geolocation_dataset.csv` | 1 por coordenada | ~1.000.163 |
| `data/bronze/olist_traducao_categoria.parquet` | `product_category_name_translation.csv` | 1 por categoria | 71 |
| `data/bronze/ibge_municipios.parquet` | API IBGE Localidades | 1 por município | 5.570 |
| `data/bronze/socioeconomico_municipios.parquet` | CSV SIDRA | 1 por município | ~5.570 |

Contagens são referência para o log, não critério de falha — variações entre versões do dataset são aceitáveis desde que registradas.

### Cache da API IBGE

Resposta bruta salva em `data/raw/ibge/municipios.json`. Se o arquivo existir e tiver menos de 30 dias, não bate na API. Todos os membros usam o **mesmo** JSON — conferir por `sha256` antes de comparar resultados.

---

## 4. Camada silver — responsável: membro 2

Tipada, limpa, deduplicada. Um arquivo por entidade, sem joins entre entidades (exceto a tradução de categoria).

### 4.1 `silver/pedidos.parquet` — grão: 1 linha por `order_id`

| Coluna | Tipo | Observação |
|---|---|---|
| `order_id` | VARCHAR | PK |
| `customer_id` | VARCHAR | FK |
| `status_pedido` | VARCHAR | Valor original, minúsculo |
| `data_compra` | TIMESTAMP | Nunca nula |
| `data_aprovacao` | TIMESTAMP | Nulo legítimo |
| `data_envio_transportadora` | TIMESTAMP | Nulo legítimo |
| `data_entrega_cliente` | TIMESTAMP | Nulo legítimo |
| `data_entrega_estimada` | TIMESTAMP | Nunca nula |
| `dias_ate_entrega` | INTEGER | `data_entrega_cliente − data_compra`, em dias inteiros; nulo se não entregue |
| `dias_atraso` | INTEGER | `data_entrega_cliente − data_entrega_estimada`; negativo = adiantado; nulo se não entregue |
| `flag_atraso` | BOOLEAN | `dias_atraso > 0`; nulo se não entregue |
| `flag_entregue` | BOOLEAN | `status_pedido = 'delivered'` |

### 4.2 `silver/itens_pedido.parquet` — grão: `order_id` + `order_item_id`

| Coluna | Tipo | Observação |
|---|---|---|
| `order_id` | VARCHAR | PK composta |
| `order_item_id` | INTEGER | PK composta |
| `product_id` | VARCHAR | FK |
| `seller_id` | VARCHAR | FK |
| `data_limite_envio` | TIMESTAMP | |
| `valor_produto` | DECIMAL(12,2) | |
| `valor_frete` | DECIMAL(12,2) | |
| `valor_total_item` | DECIMAL(12,2) | `valor_produto + valor_frete` |
| `flag_frete_outlier` | BOOLEAN | `valor_frete` acima do p99 |

**Nenhuma linha de item pode ser criada ou perdida nesta camada.** A contagem de entrada e de saída tem de bater exatamente.

### 4.3 `silver/produtos.parquet` — grão: 1 por `product_id`

| Coluna | Tipo | Observação |
|---|---|---|
| `product_id` | VARCHAR | PK |
| `categoria_pt` | VARCHAR | `'nao_informado'` quando ausente |
| `categoria_en` | VARCHAR | Via tradução; `'not_informed'` quando ausente |
| `peso_g` | DECIMAL(10,2) | Mediana da categoria quando nulo |
| `comprimento_cm`, `altura_cm`, `largura_cm` | DECIMAL(10,2) | Mediana da categoria quando nulo |
| `volume_cm3` | DECIMAL(14,2) | Produto das três dimensões |
| `qtd_fotos` | INTEGER | Zero quando nulo |
| `flag_imputado` | BOOLEAN | TRUE se qualquer medida foi imputada |

### 4.4 `silver/clientes.parquet` — grão: 1 por `customer_id`

Colunas: `customer_id` (PK), `customer_unique_id`, `cep_prefixo` (VARCHAR de 5 posições, com zeros à esquerda preservados), `cidade_origem`, `uf_origem`.

`customer_unique_id` é a identidade real da pessoa; `customer_id` é regenerado a cada pedido. **A `dim_cliente` usa `customer_unique_id` como chave natural** — usar o outro zera a taxa de recompra.

### 4.5 `silver/vendedores.parquet` — grão: 1 por `seller_id`

Colunas: `seller_id` (PK), `cep_prefixo`, `cidade_origem`, `uf_origem`.

### 4.6 `silver/pagamentos_pedido.parquet` — grão: 1 por `order_id`

Agregação das múltiplas parcelas de pagamento.

| Coluna | Tipo | Regra |
|---|---|---|
| `order_id` | VARCHAR | PK |
| `tipo_pagamento_predominante` | VARCHAR | Tipo com maior soma de `payment_value` |
| `qtd_parcelas` | INTEGER | Máximo de `payment_installments` entre os registros do tipo predominante; mínimo 1 |
| `valor_pago_total` | DECIMAL(12,2) | Soma de todas as parcelas — **conferência apenas, não é medida de faturamento** |
| `qtd_meios_pagamento` | INTEGER | Contagem distinta de tipos no pedido |

**Desempate do tipo predominante**, quando há empate na soma: ordem fixa `credit_card` → `boleto` → `debit_card` → `voucher`. O valor `not_defined` é tratado como `'nao_informado'`.

### 4.7 `silver/avaliacoes_pedido.parquet` — grão: 1 por `order_id`

**Desempate** quando o pedido tem mais de uma avaliação, nesta ordem: (1) maior `review_creation_date`; (2) maior `review_answer_timestamp`; (3) maior `review_id` em ordem lexicográfica. O critério 3 existe só para garantir determinismo — sem ele a segunda execução pode escolher outra linha.

Colunas: `order_id` (PK), `review_id`, `nota_avaliacao` (SMALLINT, 1 a 5), `data_avaliacao`, `flag_tem_comentario` (BOOLEAN). O texto do comentário não é carregado.

### 4.8 `silver/geolocalizacao_agregada.parquet` — grão: 1 por `cep_prefixo`

| Coluna | Tipo | Regra |
|---|---|---|
| `cep_prefixo` | VARCHAR | PK, 5 posições |
| `latitude`, `longitude` | DECIMAL(9,6) | **Mediana** das coordenadas do prefixo |
| `cidade_predominante`, `uf_predominante` | VARCHAR | Moda |
| `qtd_pontos` | INTEGER | Coordenadas agregadas |

Mediana e não média: há coordenadas com erro de digitação caindo fora do território nacional, e a média é arrastada por elas. Descartar antes da agregação qualquer ponto fora de `latitude ∈ [-34, 6]` e `longitude ∈ [-74, -34]`, registrando a contagem no log.

### 4.9 `silver/municipios.parquet` — grão: 1 por `cod_ibge`

Junção do JSON do IBGE com o CSV do SIDRA, feita **pelo código IBGE** (nunca por nome).

| Coluna | Tipo | Origem |
|---|---|---|
| `cod_ibge` | VARCHAR(7) | IBGE, PK |
| `municipio` | VARCHAR | IBGE, nome oficial acentuado |
| `municipio_normalizado` | VARCHAR | Derivado (ver seção 5.1) |
| `uf` | VARCHAR(2) | IBGE |
| `regiao` | VARCHAR | IBGE |
| `mesorregiao`, `microrregiao` | VARCHAR | IBGE |
| `populacao` | INTEGER | SIDRA, nulo legítimo se ausente |
| `pib_per_capita` | DECIMAL(12,2) | SIDRA, nulo legítimo se ausente |
| `porte_municipio` | VARCHAR | Derivado: `Pequeno` (< 50 mil), `Médio` (50–500 mil), `Grande` (> 500 mil), `Não informado` |

---

## 5. Integração geográfica — responsável: membro 3

### 5.1 Função de normalização (`src/utils/normalizacao.py`)

Assinatura única, usada por **todos** os membros: `normalizar_texto(s: str) -> str`.

Passos, nesta ordem: converter para minúsculas → `unicodedata.normalize('NFKD')` e remover combinantes → remover tudo que não seja letra, número ou espaço → colapsar espaços múltiplos → `strip()`.

O membro 3 é o dono deste arquivo. Ninguém escreve uma segunda implementação de normalização.

### 5.2 Dependência entre silver e integração (ponto de atenção)

As duas camadas se cruzam. Para evitar retrabalho, o contrato fixa:

- A **silver** entrega `geolocalizacao_agregada.parquet` e `municipios.parquet`, e **não** calcula distâncias.
- A **integração** consome esses dois arquivos e entrega os três da seção 5.3, incluindo `distancias`.
- A **gold** consome os três e apenas faz o lookup — não recalcula nada.

### 5.3 Saídas

**`silver/municipios_cliente.parquet` — no máximo 1 linha por `customer_id`.**
**`silver/municipios_vendedor.parquet` — no máximo 1 linha por `seller_id`.**

Ambas com as colunas:

| Coluna | Tipo | Observação |
|---|---|---|
| `customer_id` / `seller_id` | VARCHAR | PK |
| `cod_ibge` | VARCHAR(7) | Nulo se não resolvido |
| `metodo_match` | VARCHAR | `exato`, `geografico`, `de_para`, `nao_resolvido` |
| `distancia_match_km` | DECIMAL(10,2) | Preenchido apenas no método `geografico` |

A unicidade é **condição de aceite**, não recomendação: uma linha duplicada aqui multiplica itens na fato e quebra o faturamento silenciosamente. O teste roda no fim da etapa.

**`silver/distancias_vendedor_cliente.parquet` — grão: 1 por par `(seller_id, customer_id)` presente em `itens_pedido`.**
Colunas: `seller_id`, `customer_id`, `distancia_km` (Haversine entre os centroides municipais resolvidos), `flag_distancia_estimada`. Nula quando qualquer um dos lados não foi resolvido.

### 5.4 Critérios de match

1. **Exato** — igualdade de `(municipio_normalizado, uf)`. Nunca casar só por nome: "Bom Jesus" existe em vários estados.
2. **Geográfico** — mediana de lat/lng do prefixo de CEP versus centroide municipal, com aceite até **50 km**. Acima disso, marcar como não resolvido. Centroides calculados apenas a partir de prefixos já resolvidos pelo método exato, para não realimentar erro.
3. **De-para manual** — `de_para_municipios.csv` versionado, com as colunas `cidade_origem`, `uf_origem`, `cod_ibge`, `justificativa`. Preenchimento **somente com evidência** (busca do nome oficial, consulta ao CEP). Nunca por palpite.

**Saída obrigatória:** `docs/relatorio_match.md` com a taxa por método, a taxa global e a lista completa dos não resolvidos. Esse número entra no relatório final.

---

## 6. Camada gold — responsável: membro 4

### 6.1 Surrogate keys — regra de determinismo

`ROW_NUMBER() OVER (ORDER BY <chave_natural>) ` com `ORDER BY` **sempre explícito e sempre pela chave natural**, começando em 1. O membro técnico ocupa `-1` e é inserido antes.

Sem o `ORDER BY` explícito o DuckDB não garante a mesma ordem entre execuções: o critério de conclusão do grupo ("segunda execução com as mesmas chaves") falha, ou — pior — passa por acaso no desenvolvimento e falha na demonstração.

### 6.2 Dimensões

| Tabela | Chave natural (ordem da SK) | Cardinalidade esperada |
|---|---|---|
| `dim_tempo` | `data` | 1.461 (2016-01-01 a 2019-12-31) |
| `dim_produto` | `product_id` | ~32.951 |
| `dim_cliente` | `customer_unique_id` | ~96.096 |
| `dim_vendedor` | `seller_id` | ~3.095 |
| `dim_geografia` | `cod_ibge` | 5.570 |
| `dim_pagamento` | `tipo_pagamento` + `qtd_parcelas` | ~30 |

`dim_tempo` vai até 2019 porque `data_entrega_estimada` ultrapassa o fim dos pedidos. Colunas: `sk_tempo`, `data`, `ano`, `mes`, `nome_mes`, `trimestre`, `ano_mes` (`YYYY-MM`), `dia`, `dia_semana`, `nome_dia_semana`, `flag_fim_semana`.

Todas as dimensões usam **SCD Tipo 1** (sobrescrita). O dataset é um snapshot; registrar no código o comentário de que Tipo 2 seria aplicável em `dim_produto` se houvesse histórico de recategorização.

### 6.3 `fato_item_pedido` — grão: um item de um pedido

FKs: `sk_tempo_compra`, `sk_tempo_entrega`, `sk_produto`, `sk_cliente`, `sk_vendedor`, `sk_geo_cliente`, `sk_geo_vendedor`, `sk_pagamento`.
Degenerada: `order_id`.
Medidas: `valor_produto`, `valor_frete`, `valor_total_item`, `dias_ate_entrega`, `dias_atraso`, `flag_atraso`, `distancia_km`, `nota_avaliacao`, `qtd_item` (constante 1).

`sk_tempo_entrega` aponta para `-1` quando o pedido não foi entregue. `nota_avaliacao` e `dias_atraso` são atributos do pedido replicados no item: **servem para segmentar, não para calcular média** (ver seção 7).

### 6.4 `fato_pedido` — grão: um pedido

Existe para as métricas que são naturalmente por pedido. FKs: `sk_tempo_compra`, `sk_tempo_entrega`, `sk_cliente`, `sk_geo_cliente`, `sk_pagamento`. Degenerada: `order_id`.
Medidas: `valor_produtos_pedido`, `valor_frete_pedido`, `valor_total_pedido`, `qtd_itens`, `qtd_produtos_distintos`, `qtd_vendedores_distintos`, `dias_ate_entrega`, `dias_atraso`, `flag_atraso`, `nota_avaliacao`.

### 6.5 Relatório de qualidade — `data/gold/qualidade.md`

Gerado ao fim da carga, contendo:

- Contagem de órfãos por FK (critério de aceite: **zero**).
- Unicidade das PKs de todas as dimensões e das chaves compostas das fatos.
- Reconciliação: `SUM(valor_total_item)` na gold versus `SUM(valor_total_item)` na silver — diferença tolerada de R$ 0,00.
- Reconciliação cruzada: soma de `fato_item_pedido` por `order_id` versus `fato_pedido`.
- Taxa de match de municípios por método.
- Contagem de linhas por camada e por tabela.
- Contagem de membros técnicos (`sk = -1`) usados em cada FK.

---

## 7. Regras dos KPIs

Definidas aqui, uma única vez, para que os três painéis do dashboard apresentem os mesmos números.

### 7.1 Universo de análise por painel

| Painel | Status de pedido considerados |
|---|---|
| Comercial | Todos, **exceto** `canceled` e `unavailable` |
| Logística | Apenas `delivered` **e** com `data_entrega_cliente` não nula |
| Satisfação | Pedidos com avaliação, qualquer status |

Qualquer painel exibe o universo usado no rodapé. Divergência de totais entre painéis é esperada e deve ser explicada na apresentação — não é erro.

### 7.2 Definições

| KPI | Fórmula | Fato | Frete |
|---|---|---|---|
| Faturamento | `SUM(valor_produto)` | item | **excluído** |
| Faturamento bruto | `SUM(valor_total_item)` | item | incluído |
| Ticket médio | `SUM(valor_total_pedido) / COUNT(order_id)` | pedido | incluído |
| Itens por pedido | `AVG(qtd_itens)` | pedido | — |
| Tempo médio de entrega | `AVG(dias_ate_entrega)` | pedido | — |
| % de atraso | `COUNT(flag_atraso) / COUNT(order_id)` | pedido | — |
| Frete médio | `AVG(valor_frete_pedido)` | pedido | — |
| Frete sobre valor | `SUM(valor_frete) / SUM(valor_produto)` | item | — |
| Nota média | `AVG(nota_avaliacao)` | **pedido** | — |
| % detratores | `COUNT(nota <= 2) / COUNT(order_id avaliado)` | pedido | — |
| Taxa de recompra | clientes com ≥ 2 pedidos / total de clientes | pedido + `dim_cliente` | — |
| Faturamento per capita | faturamento do município / `populacao` | item + `dim_geografia` | excluído |

**Faturamento exclui frete** por decisão do grupo: frete é receita da operação logística, não da venda. A versão com frete fica disponível como medida separada.

**Nota média e % de detratores usam `fato_pedido`.** Calculá-los no grão de item pondera a satisfação pelo número de itens do pedido, o que distorce o resultado.

**`valor_pago_total` nunca é usado como faturamento.** Pagamento é por pedido e pode incluir múltiplos meios e vouchers; o faturamento vem de `price + freight_value`, que é nativo do item.

---

## 8. Responsáveis por arquivo compartilhado

| Arquivo | Dono | Alteram mediante aviso |
|---|---|---|
| `src/run_pipeline.py` | Membro 1 | — |
| `requirements.txt` | Membro 1 | — |
| `README.md` | Membro 1 | — |
| `src/utils/normalizacao.py` | Membro 3 | — |
| `de_para_municipios.csv` | Membro 3 | — |
| `docs/contratos_dados.md` | Membro 1 | Todos, via seção 9 |
| `docs/<nome>_<camada>.md` | Cada membro | — |

Cada membro documenta a própria camada em arquivo separado dentro de `docs/`, para evitar conflito de merge.

---

## 9. Processo de alteração do contrato

1. Quem identifica a necessidade abre uma issue descrevendo a mudança e o motivo.
2. Comunica no grupo **antes** de implementar.
3. Membros afetados confirmam.
4. Membro 1 atualiza este documento e incrementa a versão.
5. Só então a implementação começa.

Alterar o contrato depois que a camada seguinte já consome a tabela é a principal fonte de retrabalho no projeto. Na dúvida, pergunte antes.

---

## 10. Critério de conclusão

O projeto está pronto quando, com dados reais:

- O pipeline executa de ponta a ponta com um comando.
- Zero órfãos em todas as FKs.
- Todas as PKs únicas.
- Faturamento reconciliado entre silver e gold, e entre as duas fatos.
- A **segunda execução** produz os mesmos conteúdos, as mesmas surrogate keys e os mesmos totais da primeira.
- `docs/relatorio_match.md` e `data/gold/qualidade.md` gerados e revisados.

---

## 11. Histórico de versões

| Versão | O que mudou | Motivo |
|---|---|---|
| 1.0 | Primeira consolidação. | — |
| 1.1 | Seção 1: `data/raw/` passa a ser versionado no Git; só as saídas das camadas (`data/bronze/`, `data/silver/`, `data/gold/`, `*.parquet`, `*.duckdb`) ficam de fora. | A regra anterior (`data/` fora do Git) contradizia o repositório: as bases do Olist, o JSON do IBGE e os originais do SIDRA já estavam commitados, e é assim que o grupo garante que todos rodam sobre os mesmos bytes. |

Nenhuma alteração até aqui mexeu em nome de tabela, coluna, grão ou regra de negócio — nada do que já foi implementado precisa ser refeito.