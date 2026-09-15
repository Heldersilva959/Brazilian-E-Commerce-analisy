# Plano de qualidade do Data Warehouse

## 1. Objetivo

Este documento define as verificações de qualidade executadas após a materialização da camada Gold.

As verificações têm como objetivos:

- Confirmar que os grãos das tabelas foram preservados.
- Detectar registros duplicados.
- Garantir integridade entre fatos e dimensões.
- Reconciliar valores monetários entre Silver e Gold.
- Medir a cobertura da integração municipal.
- Verificar regras de negócio sobre entregas, pagamentos e avaliações.
- Demonstrar que o pipeline é idempotente.

O resultado da execução será registrado em:

```text
data/gold/qualidade.md
```

O relatório deverá apresentar resultados reais, incluindo valores encontrados, valores esperados e situação de cada teste.

## 2. Momento de execução

As verificações serão executadas depois da criação de:

```text
dim_tempo
dim_produto
dim_cliente
dim_vendedor
dim_geografia
dim_pagamento
fato_item_pedido
fato_pedido
```

O relatório será recriado em cada execução do pipeline.

Ordem prevista:

```text
Bronze
  ↓
Silver
  ↓
Integração municipal
  ↓
Gold
  ↓
Qualidade
```

## 3. Classificação dos testes

Cada teste terá uma das seguintes classificações:

| Classificação | Significado |
| --- | --- |
| `APROVADO` | Resultado encontrado atende ao critério |
| `REPROVADO` | Resultado viola integridade ou regra obrigatória |
| `ALERTA` | Resultado é permitido, mas precisa ser documentado |
| `NÃO EXECUTADO` | Entrada necessária estava indisponível |

### 3.1 Erros que interrompem o pipeline

Devem interromper a execução:

- Arquivo obrigatório ausente.
- Coluna obrigatória ausente.
- Chave primária nula ou duplicada.
- Violação do grão de uma tabela fato.
- Chave estrangeira órfã.
- Divergência monetária entre Silver e Gold.
- Multiplicação de itens durante os joins.
- Código IBGE duplicado na dimensão geografia.

### 3.2 Situações de alerta

Devem ser registradas, mas não interrompem automaticamente a execução:

- Cliente ou vendedor sem município resolvido.
- Município sem população ou PIB per capita.
- Produto com peso ou dimensões ainda ausentes.
- Pedido sem avaliação.
- Pedido não entregue.
- Distância que não pôde ser calculada.
- Frete sinalizado como outlier.
- Data válida encontrada fora do período inicialmente previsto.

## 4. Estrutura do resultado de um teste

Cada teste deverá informar:

| Campo | Descrição |
| --- | --- |
| `id` | Identificador estável do teste |
| `categoria` | Grupo da verificação |
| `descricao` | O que está sendo verificado |
| `esperado` | Critério de aceite |
| `encontrado` | Resultado real |
| `status` | Aprovado, reprovado ou alerta |
| `detalhes` | Informações adicionais |

Exemplo:

```text
ID: GOLD-FK-001
Categoria: Integridade referencial
Descrição: Produtos órfãos na fato_item_pedido
Esperado: 0
Encontrado: 0
Status: APROVADO
```

## 5. Inventário e contagem de linhas

O relatório deverá apresentar a quantidade de registros de cada fonte e camada.

### 5.1 Bronze

Registrar contagens para:

```text
olist_orders_dataset
olist_order_items_dataset
olist_products_dataset
olist_customers_dataset
olist_sellers_dataset
olist_order_payments_dataset
olist_order_reviews_dataset
olist_geolocation_dataset
product_category_name_translation
municipios_ibge
indicadores_municipais
```

### 5.2 Silver

Registrar contagens para:

```text
produtos
clientes
vendedores
pedidos
itens_pedido
pagamentos_pedido
avaliacoes_pedido
geografia_integrada
clientes_municipios
vendedores_municipios
distancias_itens
```

### 5.3 Gold

Registrar contagens para:

```text
dim_tempo
dim_produto
dim_cliente
dim_vendedor
dim_geografia
dim_pagamento
fato_item_pedido
fato_pedido
```

### 5.4 Critério

Mudanças de contagem causadas por agregação devem ser explicáveis.

Exemplos:

- `pagamentos_pedido` pode ter menos linhas que os pagamentos da Bronze porque possui uma linha por pedido.
- `avaliacoes_pedido` pode ter menos linhas que as avaliações da Bronze porque mantém apenas uma avaliação por pedido.
- `dim_cliente` pode ter menos linhas que `clientes.parquet` porque utiliza `customer_unique_id`.
- A fato de itens deverá preservar o grão dos itens da Silver.

## 6. Unicidade das chaves

### 6.1 Dimensões

| Teste | Chave | Resultado esperado |
| --- | --- | ---: |
| `GOLD-PK-001` | `dim_tempo.sk_tempo` | 0 duplicidades |
| `GOLD-PK-002` | `dim_tempo.data_completa` | 0 duplicidades |
| `GOLD-PK-003` | `dim_produto.sk_produto` | 0 duplicidades |
| `GOLD-PK-004` | `dim_produto.product_id` | 0 duplicidades |
| `GOLD-PK-005` | `dim_cliente.sk_cliente` | 0 duplicidades |
| `GOLD-PK-006` | `dim_cliente.customer_unique_id` | 0 duplicidades |
| `GOLD-PK-007` | `dim_vendedor.sk_vendedor` | 0 duplicidades |
| `GOLD-PK-008` | `dim_vendedor.seller_id` | 0 duplicidades |
| `GOLD-PK-009` | `dim_geografia.sk_geografia` | 0 duplicidades |
| `GOLD-PK-010` | `dim_geografia.cod_ibge` | 0 duplicidades |
| `GOLD-PK-011` | `dim_pagamento.sk_pagamento` | 0 duplicidades |
| `GOLD-PK-012` | Chave natural de pagamento | 0 duplicidades |

Os membros técnicos com chave `0` participam normalmente da verificação de unicidade.

Para dimensões com membro técnico, a chave natural do registro `0` poderá utilizar um valor reservado, como `nao_informado`.

### 6.2 Fatos

| Teste | Grão | Resultado esperado |
| --- | --- | ---: |
| `GOLD-GRAO-001` | `fato_item_pedido(order_id, order_item_id)` | 0 duplicidades |
| `GOLD-GRAO-002` | `fato_pedido.order_id` | 0 duplicidades |

### 6.3 Consulta de referência

```sql
SELECT COUNT(*) AS quantidade_grupos_duplicados
FROM (
    SELECT
        order_id,
        order_item_id
    FROM fato_item_pedido
    GROUP BY order_id, order_item_id
    HAVING COUNT(*) > 1
);
```

Resultado esperado:

```text
0
```

## 7. Chaves primárias nulas

Nenhuma surrogate key poderá ser nula.

Exemplo:

```sql
SELECT COUNT(*) AS quantidade
FROM dim_produto
WHERE sk_produto IS NULL;
```

Resultado esperado:

```text
0
```

Também deverão ser testadas as chaves naturais das dimensões, com exceção do membro técnico quando ele usar um valor reservado.

## 8. Integridade referencial

Todas as FKs das fatos devem encontrar uma linha correspondente em suas dimensões.

### 8.1 Fato item do pedido

| Teste | FK | Dimensão | Esperado |
| --- | --- | --- | ---: |
| `GOLD-FK-001` | `sk_tempo_compra` | `dim_tempo` | 0 órfãos |
| `GOLD-FK-002` | `sk_tempo_entrega` | `dim_tempo` | 0 órfãos |
| `GOLD-FK-003` | `sk_produto` | `dim_produto` | 0 órfãos |
| `GOLD-FK-004` | `sk_cliente` | `dim_cliente` | 0 órfãos |
| `GOLD-FK-005` | `sk_vendedor` | `dim_vendedor` | 0 órfãos |
| `GOLD-FK-006` | `sk_geo_cliente` | `dim_geografia` | 0 órfãos |
| `GOLD-FK-007` | `sk_pagamento` | `dim_pagamento` | 0 órfãos |

### 8.2 Fato pedido

| Teste | FK | Dimensão | Esperado |
| --- | --- | --- | ---: |
| `GOLD-FK-008` | `sk_tempo_compra` | `dim_tempo` | 0 órfãos |
| `GOLD-FK-009` | `sk_tempo_entrega` | `dim_tempo` | 0 órfãos |
| `GOLD-FK-010` | `sk_cliente` | `dim_cliente` | 0 órfãos |
| `GOLD-FK-011` | `sk_geo_cliente` | `dim_geografia` | 0 órfãos |
| `GOLD-FK-012` | `sk_pagamento` | `dim_pagamento` | 0 órfãos |

### 8.3 Consulta de referência

```sql
SELECT COUNT(*) AS quantidade_orfaos
FROM fato_item_pedido AS fato
LEFT JOIN dim_produto AS dimensao
    ON fato.sk_produto = dimensao.sk_produto
WHERE dimensao.sk_produto IS NULL;
```

Resultado esperado:

```text
0
```

Uma FK com valor `0` não será órfã, pois deve existir um membro técnico correspondente na dimensão.

## 9. Preservação do grão

### 9.1 Fato item do pedido

A quantidade de linhas da `fato_item_pedido` deverá ser igual à quantidade de itens únicos na Silver.

```sql
SELECT COUNT(*) AS itens_silver
FROM (
    SELECT DISTINCT order_id, order_item_id
    FROM read_parquet('data/silver/itens_pedido.parquet')
);
```

```sql
SELECT COUNT(*) AS itens_gold
FROM fato_item_pedido;
```

Critério:

```text
itens_silver = itens_gold
```

Qualquer diferença reprova a carga.

### 9.2 Fato pedido

A quantidade de linhas da `fato_pedido` deverá ser igual à quantidade de pedidos únicos na Silver.

```sql
SELECT COUNT(DISTINCT order_id) AS pedidos_silver
FROM read_parquet('data/silver/pedidos.parquet');
```

```sql
SELECT COUNT(*) AS pedidos_gold
FROM fato_pedido;
```

Critério:

```text
pedidos_silver = pedidos_gold
```

### 9.3 Preservação dos identificadores

Também deverão ser procurados:

- Itens Silver ausentes na Gold.
- Itens Gold inexistentes na Silver.
- Pedidos Silver ausentes na Gold.
- Pedidos Gold inexistentes na Silver.

Não basta comparar somente as contagens, pois duas diferenças poderiam se compensar.

## 10. Reconciliação monetária

A reconciliação será feita entre `itens_pedido.parquet` e `fato_item_pedido`.

### 10.1 Medidas comparadas

| Teste | Silver | Gold | Critério |
| --- | --- | --- | --- |
| `GOLD-REC-001` | Soma de `valor_produto` | Soma de `valor_produto` | Igualdade |
| `GOLD-REC-002` | Soma de `valor_frete` | Soma de `valor_frete` | Igualdade |
| `GOLD-REC-003` | Soma de `valor_total_item` | Soma de `valor_total_item` | Igualdade |

### 10.2 Consulta de referência

```sql
WITH silver AS (
    SELECT
        SUM(valor_produto) AS valor_produto,
        SUM(valor_frete) AS valor_frete,
        SUM(valor_total_item) AS valor_total
    FROM read_parquet('data/silver/itens_pedido.parquet')
),
gold AS (
    SELECT
        SUM(valor_produto) AS valor_produto,
        SUM(valor_frete) AS valor_frete,
        SUM(valor_total_item) AS valor_total
    FROM fato_item_pedido
)
SELECT
    silver.valor_produto AS silver_produto,
    gold.valor_produto AS gold_produto,
    silver.valor_frete AS silver_frete,
    gold.valor_frete AS gold_frete,
    silver.valor_total AS silver_total,
    gold.valor_total AS gold_total
FROM silver
CROSS JOIN gold;
```

Os valores deverão usar `DECIMAL(18,2)`. Não será usada tolerância de ponto flutuante para valores monetários.

### 10.3 Regra por item

Além das somas gerais:

```sql
SELECT COUNT(*) AS quantidade_erros
FROM fato_item_pedido
WHERE valor_total_item
      IS DISTINCT FROM valor_produto + valor_frete;
```

Resultado esperado:

```text
0
```

### 10.4 Pagamentos

`valor_pagamento_total` não será reconciliado diretamente com o valor dos itens como requisito de igualdade.

O pagamento pode conter diferenças causadas pelas regras comerciais da plataforma. Ele será apresentado apenas como comparação de auditoria.

O valor de pagamentos também não será somado na `fato_item_pedido`, pois pertence ao grão de pedido.

## 11. Qualidade das entregas

### 11.1 Pedidos não entregues

```sql
SELECT COUNT(*) AS quantidade_erros
FROM fato_pedido
WHERE flag_entregue = FALSE
  AND (
      dias_ate_entrega IS NOT NULL
      OR dias_atraso IS NOT NULL
      OR flag_atraso IS NOT NULL
  );
```

Resultado esperado:

```text
0
```

### 11.2 Consistência do atraso

```sql
SELECT COUNT(*) AS quantidade_erros
FROM fato_pedido
WHERE
    (flag_atraso = TRUE AND dias_atraso <= 0)
    OR
    (flag_atraso = FALSE AND dias_atraso > 0);
```

Resultado esperado:

```text
0
```

### 11.3 Data da entrega

Para pedidos classificados como entregues, casos sem data real de entrega devem ser apresentados como alerta.

Não devem ser removidos ou ter uma data inventada.

### 11.4 Métricas de prazo

A média de prazo e a taxa de atraso serão calculadas somente com pedidos:

- Com `status_pedido = 'delivered'`.
- Com datas necessárias válidas.
- Com resultado de prazo não nulo.

O relatório deverá informar quantos pedidos formaram o denominador.

## 12. Qualidade das avaliações

### 12.1 Faixa da nota

```sql
SELECT COUNT(*) AS quantidade_erros
FROM fato_pedido
WHERE nota_avaliacao IS NOT NULL
  AND nota_avaliacao NOT BETWEEN 1 AND 5;
```

Resultado esperado:

```text
0
```

### 12.2 Pedidos sem avaliação

A quantidade e o percentual de pedidos sem avaliação serão registrados como informação.

A ausência de avaliação não será substituída por nota zero.

### 12.3 Comparação entre fatos

Como a nota é repetida nos itens, todos os itens de um mesmo pedido deverão apresentar a mesma nota consolidada.

```sql
SELECT COUNT(*) AS quantidade_pedidos_inconsistentes
FROM (
    SELECT order_id
    FROM fato_item_pedido
    GROUP BY order_id
    HAVING COUNT(DISTINCT nota_avaliacao) > 1
);
```

Resultado esperado:

```text
0
```

A satisfação média oficial do projeto será calculada na `fato_pedido`.

## 13. Qualidade dos pagamentos

Deverão ser verificados:

- Um registro de pagamento consolidado por pedido.
- Tipo predominante pertencente ao conjunto de tipos observado.
- Quantidade de parcelas não negativa.
- Faixa de parcelas coerente com a quantidade.
- Pedidos sem pagamento direcionados ao membro técnico da dimensão.

O valor monetário do pagamento não será multiplicado pelos itens.

Uma consulta de controle deverá demonstrar que `fato_item_pedido` não possui `valor_pagamento_total` como medida somável.

## 14. Integração municipal

### 14.1 Taxa de match dos clientes

A taxa principal será calculada sobre `customer_id`:

```text
clientes com cod_ibge identificado
-----------------------------------
total de customer_id
```

O relatório deverá informar:

- Total de clientes.
- Match exato.
- Match geográfico.
- Match manual.
- Não resolvidos.
- Taxa total de match.

### 14.2 Taxa de match dos vendedores

A mesma medição será realizada sobre `seller_id`.

### 14.3 Consistência dos métodos

Métodos permitidos:

```text
exato
geografico
manual
nao_resolvido
```

Regras:

- `nao_resolvido` implica `cod_ibge` nulo.
- `exato`, `geografico` e `manual` implicam `cod_ibge` preenchido.
- O código encontrado deve existir em `dim_geografia`.
- O match deve respeitar a UF.
- Match geográfico deve possuir distância de match.
- Match exato não precisa possuir distância de match.

### 14.4 Casos não resolvidos

Os casos não resolvidos serão persistidos em:

```text
data/silver/municipios_nao_resolvidos.csv
```

A presença desses casos gera `ALERTA`, não reprovação automática.

Na Gold, eles serão associados ao membro técnico:

```text
sk_geografia = 0
```

### 14.5 Cobertura socioeconômica

O relatório deverá apresentar:

- Municípios sem população estimada.
- Municípios sem PIB per capita.
- Clientes associados a municípios sem indicadores.
- Pedidos associados a municípios sem indicadores.

Ausência de indicador não será transformada em zero.

## 15. Qualidade das distâncias

Deverão ser contabilizados:

- Itens com distância calculada.
- Itens sem distância.
- Motivos de ausência.
- Distância mínima, mediana, média, p95, p99 e máxima.

Regras:

- Distância negativa é inválida e reprova o teste.
- Distância nula é permitida quando faltarem coordenadas válidas.
- Coordenadas suspeitas devem ser reportadas.
- Distâncias extremas devem ser investigadas, sem exclusão automática.

A distância representa Haversine entre pontos aproximados dos prefixos de CEP, e não distância rodoviária.

## 16. Produtos e imputações

O relatório deverá apresentar:

- Produtos com categoria `nao_informado`.
- Produtos com peso imputado.
- Produtos com dimensões imputadas.
- Produtos cujo peso continuou nulo.
- Produtos cujas dimensões continuaram nulas.
- Itens vendidos associados a esses produtos.

Regras:

- Produto sem categoria não pode ser descartado.
- Imputação deve usar a mediana da categoria.
- Flags de imputação devem refletir alterações reais.
- Valor nulo sem possibilidade de imputação permanece nulo.

## 17. Outliers de frete

O relatório deverá apresentar:

- Regra utilizada para identificar outlier.
- Quantidade e percentual de itens sinalizados.
- Valor mínimo, mediana, p99 e máximo do frete.
- Soma do frete original.
- Indicação de uso ou não de winsorização.

Por padrão:

```text
winsorização desativada
```

Outliers não serão removidos. A Gold utilizará o valor original do frete para reconciliação.

## 18. Idempotência

O pipeline será executado duas vezes consecutivas com as mesmas entradas.

Devem permanecer iguais:

- Quantidade de linhas de cada tabela.
- Chaves substitutas associadas às mesmas chaves naturais.
- Soma dos valores monetários.
- Quantidade de órfãos.
- Taxa de match municipal.
- Lista de casos não resolvidos.
- Conteúdo lógico das tabelas.

### 18.1 Assinatura lógica

Para tabelas relevantes, poderá ser calculado um hash a partir de todas as colunas ordenadas pela chave estável.

Não será exigido que o arquivo físico `dw.duckdb` tenha exatamente os mesmos bytes, pois metadados internos podem mudar sem alteração do conteúdo.

### 18.2 Chaves substitutas

Exemplo de verificação entre execuções:

```text
product_id → sk_produto
customer_unique_id → sk_cliente
seller_id → sk_vendedor
cod_ibge → sk_geografia
```

Cada associação deverá permanecer igual.

## 19. Formato do relatório final

O arquivo `data/gold/qualidade.md` deverá conter:

```markdown
# Relatório de qualidade

## Resumo executivo

- Testes executados:
- Aprovados:
- Alertas:
- Reprovados:
- Resultado geral:

## Contagens por camada

## Unicidade e grãos

## Integridade referencial

## Reconciliação monetária

## Entregas e atrasos

## Avaliações

## Integração municipal

## Indicadores socioeconômicos

## Distâncias

## Produtos e imputações

## Outliers de frete

## Idempotência

## Casos que exigem atenção
```

### 19.1 Tabela dos testes

O relatório deverá incluir uma tabela como:

| ID | Verificação | Esperado | Encontrado | Status |
| --- | --- | ---: | ---: | --- |
| `GOLD-GRAO-001` | Itens duplicados | 0 | Valor real | Status real |
| `GOLD-FK-001` | Produto órfão | 0 | Valor real | Status real |
| `GOLD-REC-001` | Diferença no valor dos produtos | 0,00 | Valor real | Status real |

O relatório não deverá apresentar resultados previamente preenchidos como se fossem resultados reais.

## 20. Resultado geral

O resultado geral será:

### APROVADO

Quando:

- Não houver testes reprovados.
- FKs não tiverem órfãos.
- PKs e grãos forem únicos.
- Valores monetários estiverem reconciliados.
- Contagens das fatos estiverem preservadas.

### APROVADO COM ALERTAS

Quando:

- Não houver testes reprovados.
- Existirem ausências legítimas ou limitações documentadas.

Exemplos:

- Municípios não resolvidos.
- PIB per capita ausente.
- Distâncias não calculadas.
- Produtos sem medidas suficientes para imputação.

### REPROVADO

Quando houver pelo menos uma falha estrutural ou divergência obrigatória.

O pipeline deverá finalizar com erro após persistir o relatório contendo as falhas encontradas.

## 21. Critérios mínimos para apresentação

Antes da apresentação, o grupo deverá possuir evidência de:

- Zero órfãos em todas as FKs.
- Zero duplicidade nas PKs.
- Zero duplicidade no grão das fatos.
- Mesmos totais monetários na Silver e Gold.
- Taxa real de match dos municípios.
- Lista real dos casos não resolvidos.
- Contagem de linhas por camada.
- Segunda execução com os mesmos resultados lógicos.
- Explicação dos alertas que permaneceram.