# Catálogo de KPIs

## 1. Objetivo

Este documento define os indicadores utilizados para analisar vendas, logística, satisfação e características socioeconômicas dos municípios.

Para cada KPI são especificados:

- Objetivo.
- Tabela fato adequada.
- Fórmula.
- Filtros.
- Tratamento de valores nulos.
- Dimensões aplicáveis.
- Cuidados de interpretação.

Os KPIs serão calculados sobre as tabelas materializadas em:

```text
data/gold/dw.duckdb
```

## 2. Convenções gerais

### 2.1 Grãos analíticos

O modelo possui duas tabelas fato:

| Fato | Grão | Uso principal |
| --- | --- | --- |
| `fato_item_pedido` | Um item de um pedido | Valores, produtos, fretes e vendedores |
| `fato_pedido` | Um pedido | Ticket médio, entregas, satisfação e recompra |

Avaliação, prazo e atraso pertencem ao pedido. Por isso, seus indicadores gerais serão calculados com `fato_pedido`.

### 2.2 Período

O período será filtrado pela data da compra:

```text
dim_tempo.data_completa
```

A dimensão tempo será ligada por:

```text
fato.sk_tempo_compra = dim_tempo.sk_tempo
```

### 2.3 Valores monetários

Os valores monetários serão tratados como `DECIMAL(18,2)`.

```text
valor_total_item = valor_produto + valor_frete
```

```text
valor_total_pedido = valor_produtos + valor_frete
```

O valor registrado nos pagamentos não será usado como medida de vendas na fato de itens.

### 2.4 Status dos pedidos

Para evitar ambiguidade, serão utilizados dois conceitos:

- **Valor movimentado:** soma dos itens registrados, independentemente do status do pedido.
- **Valor entregue:** soma dos itens pertencentes a pedidos com status `delivered`.

Quando o termo “vendas” for utilizado sem complemento no dashboard ou relatório, deverá ser informado qual dos dois conceitos está sendo aplicado.

O projeto não tratará esses valores como receita contábil oficialmente reconhecida.

### 2.5 Nulos

Regras gerais:

- Nota ausente não será convertida para zero.
- Prazo ausente não será convertido para zero.
- Pedido não entregue não será considerado pontual.
- Município não resolvido será associado ao membro técnico da dimensão geografia.
- Indicador socioeconômico ausente não será convertido para zero.
- Distância ausente será excluída somente do denominador dos indicadores que dependem de distância.

## 3. Resumo dos KPIs

| Código | KPI | Fato principal |
| --- | --- | --- |
| `KPI-VEN-001` | Valor movimentado | `fato_item_pedido` |
| `KPI-VEN-002` | Valor entregue | `fato_item_pedido` |
| `KPI-VEN-003` | Valor dos produtos entregues | `fato_item_pedido` |
| `KPI-VEN-004` | Valor de frete entregue | `fato_item_pedido` |
| `KPI-VEN-005` | Quantidade de pedidos | `fato_pedido` |
| `KPI-VEN-006` | Quantidade de itens | `fato_item_pedido` |
| `KPI-VEN-007` | Ticket médio | `fato_pedido` |
| `KPI-VEN-008` | Itens por pedido | `fato_pedido` |
| `KPI-FRE-001` | Percentual de frete | `fato_item_pedido` |
| `KPI-LOG-001` | Prazo médio de entrega | `fato_pedido` |
| `KPI-LOG-002` | Percentual de pedidos atrasados | `fato_pedido` |
| `KPI-LOG-003` | Dias médios de atraso | `fato_pedido` |
| `KPI-LOG-004` | Antecedência média | `fato_pedido` |
| `KPI-LOG-005` | Distância média | `fato_item_pedido` |
| `KPI-SAT-001` | Nota média | `fato_pedido` |
| `KPI-SAT-002` | Percentual de avaliações positivas | `fato_pedido` |
| `KPI-SAT-003` | Percentual de avaliações negativas | `fato_pedido` |
| `KPI-SAT-004` | Cobertura de avaliações | `fato_pedido` |
| `KPI-CLI-001` | Quantidade de clientes compradores | `fato_pedido` |
| `KPI-CLI-002` | Taxa de recompra | `fato_pedido` |
| `KPI-GEO-001` | Taxa de match municipal | Integração municipal |
| `KPI-GEO-002` | Valor entregue por porte municipal | Fato + `dim_geografia` |
| `KPI-GEO-003` | Ticket médio por porte municipal | Fato + `dim_geografia` |

## 4. Indicadores de vendas

### 4.1 Valor movimentado

**Código:** `KPI-VEN-001`

**Objetivo:** medir o valor total dos itens registrados no Olist, incluindo frete.

**Fato:** `fato_item_pedido`

**Fórmula:**

```text
SUM(valor_total_item)
```

**Filtros:** nenhum filtro obrigatório de status.

**Unidade:** reais.

**Consulta de referência:**

```sql
SELECT
    SUM(valor_total_item) AS valor_movimentado
FROM fato_item_pedido;
```

**Interpretação:** representa o valor dos itens existentes no dataset. Pode incluir pedidos cancelados ou não entregues e, portanto, não deve ser apresentado como receita reconhecida.

### 4.2 Valor entregue

**Código:** `KPI-VEN-002`

**Objetivo:** medir o valor dos itens de pedidos entregues.

**Fato:** `fato_item_pedido`

**Fórmula:**

```text
SUM(valor_total_item)
```

**Filtro:**

```text
status_pedido = 'delivered'
```

Como `status_pedido` está na `fato_pedido`, o cálculo deverá ligar as duas fatos por `order_id`, garantindo uma linha de pedido para cada pedido.

```sql
SELECT
    SUM(item.valor_total_item) AS valor_entregue
FROM fato_item_pedido AS item
JOIN fato_pedido AS pedido
    ON item.order_id = pedido.order_id
WHERE pedido.status_pedido = 'delivered';
```

**Unidade:** reais.

**Interpretação:** representa preço mais frete dos pedidos entregues.

### 4.3 Valor dos produtos entregues

**Código:** `KPI-VEN-003`

**Fórmula:**

```text
SUM(valor_produto)
```

**Filtro:**

```text
status_pedido = 'delivered'
```

**Unidade:** reais.

Esse indicador não inclui o frete.

### 4.4 Valor de frete entregue

**Código:** `KPI-VEN-004`

**Fórmula:**

```text
SUM(valor_frete)
```

**Filtro:**

```text
status_pedido = 'delivered'
```

**Unidade:** reais.

Os valores sinalizados como outliers continuarão no cálculo. Caso uma análise use valor winsorizado, isso deverá aparecer explicitamente no título do indicador.

### 4.5 Quantidade de pedidos

**Código:** `KPI-VEN-005`

**Fato:** `fato_pedido`

**Fórmula:**

```text
COUNT(*)
```

**Consulta:**

```sql
SELECT COUNT(*) AS quantidade_pedidos
FROM fato_pedido;
```

Para contar apenas entregas:

```sql
SELECT COUNT(*) AS quantidade_pedidos_entregues
FROM fato_pedido
WHERE status_pedido = 'delivered';
```

O título do indicador deverá informar se considera todos os pedidos ou apenas os entregues.

### 4.6 Quantidade de itens

**Código:** `KPI-VEN-006`

**Fato:** `fato_item_pedido`

**Fórmula:**

```text
COUNT(*)
```

Cada linha representa uma unidade de item do pedido segundo o grão do dataset.

### 4.7 Ticket médio

**Código:** `KPI-VEN-007`

**Objetivo:** medir o valor médio por pedido.

**Fato:** `fato_pedido`

**Fórmula:**

```text
SUM(valor_total_pedido)
-----------------------
quantidade de pedidos
```

Equivalente a:

```sql
SELECT
    AVG(valor_total_pedido) AS ticket_medio
FROM fato_pedido
WHERE status_pedido = 'delivered';
```

**Filtro padrão:** pedidos entregues.

**Unidade:** reais por pedido.

Pedidos sem itens e com total zero permanecem no conjunto se estiverem entregues. Caso sejam encontrados, sua quantidade deverá ser informada como alerta de qualidade.

O ticket médio não será calculado pela média de `valor_total_item`, pois isso produziria valor médio por item.

### 4.8 Quantidade média de itens por pedido

**Código:** `KPI-VEN-008`

**Fato:** `fato_pedido`

**Fórmula:**

```text
SUM(quantidade_itens)
---------------------
quantidade de pedidos
```

**Filtro padrão:** pedidos entregues.

```sql
SELECT
    AVG(quantidade_itens) AS itens_por_pedido
FROM fato_pedido
WHERE status_pedido = 'delivered';
```

## 5. Indicador de frete

### 5.1 Percentual de frete sobre o valor entregue

**Código:** `KPI-FRE-001`

**Objetivo:** medir quanto o frete representa no valor total entregue.

**Fórmula:**

```text
SUM(valor_frete)
------------------------- × 100
SUM(valor_total_item)
```

**Fato:** `fato_item_pedido`

**Filtro:** pedidos entregues.

```sql
SELECT
    100.0 * SUM(item.valor_frete)
    / NULLIF(SUM(item.valor_total_item), 0) AS percentual_frete
FROM fato_item_pedido AS item
JOIN fato_pedido AS pedido
    ON item.order_id = pedido.order_id
WHERE pedido.status_pedido = 'delivered';
```

**Unidade:** percentual.

Deve ser calculada a razão das somas. A média dos percentuais individuais dos itens produziria outro indicador.

## 6. Indicadores logísticos

### 6.1 Prazo médio de entrega

**Código:** `KPI-LOG-001`

**Objetivo:** medir quantos dias um pedido entregue levou para chegar ao cliente.

**Fato:** `fato_pedido`

**Fórmula:**

```text
AVG(dias_ate_entrega)
```

**Filtros:**

```text
status_pedido = 'delivered'
dias_ate_entrega IS NOT NULL
```

```sql
SELECT
    AVG(dias_ate_entrega) AS prazo_medio_entrega,
    COUNT(*) AS pedidos_avaliados
FROM fato_pedido
WHERE status_pedido = 'delivered'
  AND dias_ate_entrega IS NOT NULL;
```

**Unidade:** dias.

O denominador deverá ser exibido ou ficar disponível no relatório.

### 6.2 Percentual de pedidos atrasados

**Código:** `KPI-LOG-002`

**Objetivo:** medir a proporção de entregas realizadas após a data estimada.

**Fórmula:**

```text
pedidos com flag_atraso = true
-------------------------------- × 100
pedidos entregues avaliáveis
```

**Filtros do denominador:**

```text
status_pedido = 'delivered'
flag_atraso IS NOT NULL
```

```sql
SELECT
    100.0 * COUNT(*) FILTER (WHERE flag_atraso = TRUE)
    / NULLIF(COUNT(*) FILTER (WHERE flag_atraso IS NOT NULL), 0)
        AS percentual_atraso
FROM fato_pedido
WHERE status_pedido = 'delivered';
```

Pedidos não entregues não entram no numerador nem no denominador.

### 6.3 Dias médios de atraso

**Código:** `KPI-LOG-003`

**Objetivo:** medir a intensidade do atraso entre os pedidos efetivamente atrasados.

**Fórmula:**

```text
AVG(dias_atraso)
```

**Filtros:**

```text
status_pedido = 'delivered'
flag_atraso = true
dias_atraso IS NOT NULL
```

**Unidade:** dias.

Esse KPI não inclui entregas antecipadas ou pontuais.

### 6.4 Antecedência média

**Código:** `KPI-LOG-004`

**Objetivo:** medir quantos dias antes do prazo os pedidos antecipados foram entregues.

Para facilitar a leitura, o valor será apresentado como positivo:

```text
AVG(ABS(dias_atraso))
```

**Filtros:**

```text
status_pedido = 'delivered'
dias_atraso < 0
```

**Unidade:** dias de antecedência.

### 6.5 Distância média vendedor–cliente

**Código:** `KPI-LOG-005`

**Objetivo:** medir a distância geodésica aproximada percorrida pelos itens.

**Fato:** `fato_item_pedido`

**Fórmula:**

```text
AVG(distancia_km)
```

**Filtros:**

```text
status_pedido = 'delivered'
distancia_km IS NOT NULL
```

**Unidade:** quilômetros por item.

```sql
SELECT
    AVG(item.distancia_km) AS distancia_media_km,
    COUNT(*) AS itens_com_distancia
FROM fato_item_pedido AS item
JOIN fato_pedido AS pedido
    ON item.order_id = pedido.order_id
WHERE pedido.status_pedido = 'delivered'
  AND item.distancia_km IS NOT NULL;
```

O indicador será ponderado por item: um pedido com itens de três vendedores produzirá três observações.

A distância é calculada pela fórmula de Haversine entre pontos aproximados dos prefixos de CEP. Ela não representa percurso rodoviário.

## 7. Indicadores de satisfação

### 7.1 Nota média

**Código:** `KPI-SAT-001`

**Objetivo:** medir a satisfação média dos pedidos avaliados.

**Fato:** `fato_pedido`

**Fórmula:**

```text
AVG(nota_avaliacao)
```

**Filtro:**

```text
nota_avaliacao IS NOT NULL
```

```sql
SELECT
    AVG(nota_avaliacao) AS nota_media,
    COUNT(*) AS pedidos_avaliados
FROM fato_pedido
WHERE nota_avaliacao IS NOT NULL;
```

**Unidade:** pontos de 1 a 5.

Não calcular esse KPI com `fato_item_pedido`, pois pedidos com vários itens teriam peso maior.

### 7.2 Percentual de avaliações positivas

**Código:** `KPI-SAT-002`

**Definição:** avaliações com notas 4 ou 5.

**Fórmula:**

```text
pedidos com nota 4 ou 5
------------------------- × 100
pedidos avaliados
```

```sql
SELECT
    100.0 * COUNT(*) FILTER (WHERE nota_avaliacao >= 4)
    / NULLIF(COUNT(*) FILTER (
        WHERE nota_avaliacao IS NOT NULL
      ), 0) AS percentual_avaliacoes_positivas
FROM fato_pedido;
```

### 7.3 Percentual de avaliações negativas

**Código:** `KPI-SAT-003`

**Definição:** avaliações com notas 1 ou 2.

**Fórmula:**

```text
pedidos com nota 1 ou 2
------------------------- × 100
pedidos avaliados
```

A nota 3 será considerada neutra.

### 7.4 Cobertura de avaliações

**Código:** `KPI-SAT-004`

**Objetivo:** mostrar qual proporção dos pedidos possui avaliação.

**Fórmula:**

```text
pedidos com avaliação
----------------------- × 100
total de pedidos
```

```sql
SELECT
    100.0 * COUNT(*) FILTER (
        WHERE nota_avaliacao IS NOT NULL
    ) / NULLIF(COUNT(*), 0) AS cobertura_avaliacoes
FROM fato_pedido;
```

Esse indicador ajuda a contextualizar a nota média.

## 8. Indicadores de clientes

### 8.1 Quantidade de clientes compradores

**Código:** `KPI-CLI-001`

**Objetivo:** contar clientes únicos com pedidos válidos para a análise comercial.

**Fato:** `fato_pedido`

**Dimensão:** `dim_cliente`

**Fórmula:**

```text
COUNT(DISTINCT customer_unique_id)
```

**Filtro padrão:**

```text
status_pedido = 'delivered'
```

```sql
SELECT
    COUNT(DISTINCT cliente.customer_unique_id)
        AS clientes_compradores
FROM fato_pedido AS pedido
JOIN dim_cliente AS cliente
    ON pedido.sk_cliente = cliente.sk_cliente
WHERE pedido.status_pedido = 'delivered'
  AND pedido.sk_cliente <> 0;
```

O membro técnico não participa da contagem.

### 8.2 Taxa de recompra

**Código:** `KPI-CLI-002`

**Objetivo:** medir a proporção de clientes que realizaram mais de um pedido entregue.

**Unidade de análise:** `customer_unique_id`.

**Definição de cliente recorrente:**

```text
cliente com pelo menos dois order_id distintos entregues
```

**Fórmula:**

```text
clientes com mais de um pedido entregue
----------------------------------------- × 100
clientes com ao menos um pedido entregue
```

```sql
WITH pedidos_por_cliente AS (
    SELECT
        cliente.customer_unique_id,
        COUNT(DISTINCT pedido.order_id) AS quantidade_pedidos
    FROM fato_pedido AS pedido
    JOIN dim_cliente AS cliente
        ON pedido.sk_cliente = cliente.sk_cliente
    WHERE pedido.status_pedido = 'delivered'
      AND pedido.sk_cliente <> 0
    GROUP BY cliente.customer_unique_id
)
SELECT
    100.0 * COUNT(*) FILTER (
        WHERE quantidade_pedidos > 1
    ) / NULLIF(COUNT(*), 0) AS taxa_recompra
FROM pedidos_por_cliente;
```

Não utilizar `customer_id`, pois esse identificador pode ser regenerado a cada pedido.

A taxa de recompra deve ser calculada no período completo ou em uma coorte claramente definida. Quando houver filtro de datas, compras anteriores fora do intervalo não estarão sendo consideradas.

## 9. Indicadores geográficos e socioeconômicos

### 9.1 Taxa de match municipal

**Código:** `KPI-GEO-001`

**Objetivo:** medir a cobertura da integração entre clientes Olist e municípios IBGE.

**Fonte:** `clientes_municipios.parquet` ou relatório persistido pela integração.

**Fórmula:**

```text
customer_id com cod_ibge resolvido
----------------------------------- × 100
total de customer_id
```

O resultado deverá ser detalhado pelos métodos:

```text
exato
geografico
manual
nao_resolvido
```

Esse KPI mede qualidade da integração, não desempenho comercial.

### 9.2 Valor entregue por porte municipal

**Código:** `KPI-GEO-002`

**Objetivo:** comparar o valor entregue conforme o porte populacional do município do cliente.

**Fato:** `fato_item_pedido`

**Dimensão:** `dim_geografia`

**Medida:**

```text
SUM(valor_total_item)
```

**Agrupamento:**

```text
porte_municipio
```

**Filtro:**

```text
status_pedido = 'delivered'
```

Municípios não resolvidos deverão aparecer como `nao_informado`, em vez de serem excluídos silenciosamente.

### 9.3 Ticket médio por porte municipal

**Código:** `KPI-GEO-003`

**Fato:** `fato_pedido`

**Fórmula por porte:**

```text
SUM(valor_total_pedido)
-----------------------
quantidade de pedidos
```

**Filtros:**

```text
status_pedido = 'delivered'
```

Indicadores socioeconômicos são referentes a 2017 e serão tratados como contexto fixo dos municípios durante o período de vendas.

## 10. Análises complementares

As análises abaixo não precisam ser exibidas como cartões de KPI, mas são úteis na apresentação.

### 10.1 Atraso e satisfação

Comparar a nota média entre pedidos atrasados e não atrasados.

```sql
SELECT
    flag_atraso,
    AVG(nota_avaliacao) AS nota_media,
    COUNT(*) AS pedidos
FROM fato_pedido
WHERE status_pedido = 'delivered'
  AND flag_atraso IS NOT NULL
  AND nota_avaliacao IS NOT NULL
GROUP BY flag_atraso;
```

Essa comparação demonstra associação. Ela não prova que o atraso causou a nota.

### 10.2 Distância e atraso

Agrupar os itens em faixas de distância e comparar:

- Percentual de atraso.
- Prazo médio.
- Nota média.

Como prazo e nota pertencem ao pedido, a análise por item pode dar mais peso a pedidos com muitos itens. Essa limitação deve ser declarada.

### 10.3 PIB per capita e ticket médio

Agrupar municípios por faixas de PIB per capita e comparar o ticket médio dos pedidos entregues.

Não interpretar uma associação agregada como comportamento individual dos consumidores.

### 10.4 Categorias mais vendidas

**Fato:** `fato_item_pedido`

Métricas possíveis por categoria:

- Quantidade de itens.
- Valor dos produtos.
- Valor total incluindo frete.
- Frete médio.
- Nota média associada aos pedidos.

Para nota média por categoria, deixar claro que um pedido com itens de várias categorias contribui para cada categoria correspondente.

### 10.5 Desempenho dos vendedores

**Fato:** `fato_item_pedido`

Métricas possíveis:

- Quantidade de itens vendidos.
- Valor entregue.
- Frete médio.
- Distância média.
- Percentual de itens associados a pedidos atrasados.
- Nota média dos pedidos relacionados.

Pedidos com vários vendedores impedem atribuir integralmente a avaliação ou o atraso a apenas um vendedor. A análise mostra associação entre o vendedor e o pedido.

## 11. Dimensões de análise

Os KPIs poderão ser segmentados por:

| Dimensão | Exemplos |
| --- | --- |
| Tempo | Ano, trimestre, mês e dia da semana |
| Produto | Categoria, faixa de preço e faixa de peso |
| Cliente | Cliente único para análise de recompra |
| Vendedor | Vendedor, cidade, UF e região |
| Geografia | Município, UF, região e porte |
| Pagamento | Tipo predominante e faixa de parcelas |

Nem toda combinação será válida.

Exemplos:

- Nota média por categoria exige atenção ao peso dos itens.
- Satisfação geral deve vir da fato de pedidos.
- Vendas por vendedor devem vir da fato de itens.
- Recompra deve utilizar `customer_unique_id`.

## 12. Indicadores de apoio

Todo KPI médio ou percentual deverá ser acompanhado por sua base de cálculo.

Exemplos:

| KPI principal | Indicador de apoio |
| --- | --- |
| Nota média | Quantidade de pedidos avaliados |
| Prazo médio | Quantidade de entregas com prazo calculável |
| Percentual de atraso | Quantidade de entregas avaliáveis |
| Distância média | Quantidade de itens com distância |
| Ticket médio | Quantidade de pedidos incluídos |
| Taxa de recompra | Quantidade de clientes compradores |
| PIB per capita médio | Quantidade de municípios com PIB disponível |

Isso evita apresentar uma média sem informar a cobertura dos dados.

## 13. Regras para filtros no dashboard

O dashboard deverá deixar visíveis os filtros que alteram o significado dos KPIs.

Filtros recomendados:

- Período da compra.
- Status do pedido.
- Categoria do produto.
- UF ou região do cliente.
- UF ou região do vendedor.
- Porte do município.
- Tipo predominante de pagamento.
- Faixa de parcelas.

Para KPIs com definição fixa, o filtro obrigatório deve permanecer explícito.

Exemplo:

```text
Prazo médio — somente pedidos entregues com datas válidas
```

## 14. KPIs prioritários para apresentação

Para uma apresentação curta, recomenda-se destacar:

1. Valor total entregue.
2. Quantidade de pedidos entregues.
3. Ticket médio dos pedidos entregues.
4. Prazo médio de entrega.
5. Percentual de pedidos atrasados.
6. Nota média dos pedidos avaliados.
7. Taxa de recompra.
8. Taxa de match municipal.

Visualizações complementares:

- Valor entregue por mês.
- Percentual de atraso por UF.
- Nota média entre pedidos atrasados e não atrasados.
- Ticket médio por porte municipal.
- Categorias com maior valor entregue.

## 15. Decisões adotadas

| Tema | Decisão |
| --- | --- |
| Valor principal de vendas | Preço do produto mais frete |
| Valor entregue | Somente pedidos com status `delivered` |
| Ticket médio | Calculado na `fato_pedido` |
| Prazo médio | Somente entregues com datas válidas |
| Taxa de atraso | Somente entregas avaliáveis |
| Satisfação média | Uma avaliação consolidada por pedido |
| Avaliação positiva | Notas 4 e 5 |
| Avaliação neutra | Nota 3 |
| Avaliação negativa | Notas 1 e 2 |
| Recompra | Mais de um pedido entregue por `customer_unique_id` |
| Distância média | Média por item com distância calculada |
| Outlier de frete | Mantido no cálculo e sinalizado |
| Indicadores municipais | Retrato fixo de 2017 |
| Município não resolvido | Exibido como `nao_informado` |

## 16. Limitações

Os resultados deverão ser apresentados considerando que:

- O dataset cobre um período e uma plataforma específicos.
- Valor entregue não equivale necessariamente a receita contábil.
- O Olist não fornece histórico completo das alterações das dimensões.
- As coordenadas são aproximações derivadas dos prefixos de CEP.
- Distância Haversine não representa rota rodoviária.
- PIB e população são atributos municipais de 2017.
- Associação entre atraso e nota não demonstra causalidade.
- Pedidos sem avaliação não participam da nota média.
- Municípios não resolvidos reduzem a cobertura das análises geográficas.