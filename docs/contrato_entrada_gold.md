# Contrato de entrada da Gold — versão 2.0

Consolidado em 2026-09-15 a pedido do usuário. Este é o contrato oficial da interface Silver → Gold; substitui as propostas de nomes, tipos e regras anteriores em `contratos_dados.md` e neste arquivo. O documento `silver_contrato.md` descreve a implementação e resultados históricos, sem definir uma interface concorrente.

O esquema executável está em `src/silver/contrato_gold.py`. Alterações de interface devem atualizar código, tabelas abaixo e validações na mesma revisão.

## 1. Convenções e aceite

- Onze arquivos Parquet obrigatórios em `data/silver/`; colunas extras são permitidas.
- Nomes físicos existentes são preservados. Nomes dimensionais podem ser diferentes, mediante projeção explícita na Gold (seção 4).
- Dinheiro: `DECIMAL(18,2)`, inclusive total do item e soma de pagamentos. Overflow deve interromper a transformação.
- Peso, medidas físicas, coordenadas e distâncias: `DOUBLE`. Contagens e diferenças de dias: `BIGINT`; identificador do item e parcelas: `INTEGER`.
- Código IBGE e CEP: `VARCHAR`, respectivamente sete e cinco dígitos. Datas: `TIMESTAMP` sem fuso.
- Colunas não nulas e chaves de grão são obrigatórias. Tipos devem corresponder exatamente; a Gold não corrige entradas por conversão silenciosa.
- Nulos legítimos de dinheiro, prazos, avaliações, coordenadas e indicadores permanecem nulos. Não viram zero.
- A etapa `validacao` verifica esquema, nulidade e grão de todas as entradas. Violações da interface reprovam o pipeline. As demais verificações BRZ/SLV/INT continuam cobrindo referências, reconciliação e regras.
- A Gold deverá chamar `verificar(con, Path('data/silver'))` e interromper a carga se a lista de violações não estiver vazia. O relatório antigo, sozinho, não comprova a validade dos arquivos atuais.

## 2. Arquivos e grãos

| Arquivo | Chave única | Produtor |
| --- | --- | --- |
| `pedidos.parquet` | `order_id` | Transformação Silver |
| `itens_pedido.parquet` | `order_id + item_pedido_id` | Transformação Silver |
| `produtos.parquet` | `product_id` | Transformação Silver |
| `clientes.parquet` | `customer_id` | Transformação Silver |
| `vendedores.parquet` | `seller_id` | Transformação Silver |
| `pagamentos.parquet` | `order_id` | Transformação Silver |
| `avaliacoes.parquet` | `order_id` | Transformação Silver |
| `geografia_integrada.parquet` | `cod_ibge` | Integração municipal |
| `distancias_itens.parquet` | `order_id + order_item_id` | Integração municipal |
| `clientes_municipios.parquet` | `customer_id` | Integração municipal |
| `vendedores_municipios.parquet` | `seller_id` | Integração municipal |

`clientes` tem uma linha por cadastro do pedido, não por pessoa; `customer_unique_id` pode repetir. Pagamentos e avaliações têm no máximo uma linha por pedido, e podem não existir para alguns pedidos. Não usar inner join para eliminar esses pedidos.

## 3. Esquema físico obrigatório

### `pedidos.parquet`

| Coluna | Tipo DuckDB | Aceita nulo |
| --- | --- | --- |
| `order_id` | `VARCHAR` | Não |
| `customer_id` | `VARCHAR` | Não |
| `status_pedido` | `VARCHAR` | Não |
| `ano_mes_compra` | `VARCHAR` | Sim |
| `ts_compra` | `TIMESTAMP` | Sim |
| `ts_aprovacao` | `TIMESTAMP` | Sim |
| `ts_envio_transportadora` | `TIMESTAMP` | Sim |
| `ts_entrega_cliente` | `TIMESTAMP` | Sim |
| `ts_estimativa_entrega` | `TIMESTAMP` | Sim |
| `dias_ate_entrega` | `BIGINT` | Sim |
| `dias_atraso` | `BIGINT` | Sim |
| `flag_entrega_ausente` | `BOOLEAN` | Não |
| `flag_atraso` | `BOOLEAN` | Sim |

### `itens_pedido.parquet`

| Coluna | Tipo DuckDB | Aceita nulo |
| --- | --- | --- |
| `order_id` | `VARCHAR` | Não |
| `product_id` | `VARCHAR` | Sim |
| `seller_id` | `VARCHAR` | Sim |
| `faixa_preco` | `VARCHAR` | Sim |
| `item_pedido_id` | `INTEGER` | Não |
| `ts_limite_envio` | `TIMESTAMP` | Sim |
| `preco_produto` | `DECIMAL(18,2)` | Sim |
| `valor_frete` | `DECIMAL(18,2)` | Sim |
| `valor_total_item` | `DECIMAL(18,2)` | Sim |
| `flag_frete_outlier` | `BOOLEAN` | Sim |

### `produtos.parquet`

| Coluna | Tipo DuckDB | Aceita nulo |
| --- | --- | --- |
| `product_id` | `VARCHAR` | Não |
| `categoria_produto` | `VARCHAR` | Não |
| `categoria_produto_ingles` | `VARCHAR` | Não |
| `peso_g` | `DOUBLE` | Sim |
| `comprimento_cm` | `DOUBLE` | Sim |
| `altura_cm` | `DOUBLE` | Sim |
| `largura_cm` | `DOUBLE` | Sim |
| `flag_categoria_sem_traducao` | `BOOLEAN` | Não |
| `flag_peso_imputado` | `BOOLEAN` | Não |
| `flag_dimensoes_imputadas` | `BOOLEAN` | Não |

### `clientes.parquet`

| Coluna | Tipo DuckDB | Aceita nulo |
| --- | --- | --- |
| `customer_id` | `VARCHAR` | Não |
| `customer_unique_id` | `VARCHAR` | Não |
| `cep_prefixo` | `VARCHAR` | Sim |
| `cidade` | `VARCHAR` | Sim |
| `uf` | `VARCHAR` | Sim |

### `vendedores.parquet`

| Coluna | Tipo DuckDB | Aceita nulo |
| --- | --- | --- |
| `seller_id` | `VARCHAR` | Não |
| `cep_prefixo` | `VARCHAR` | Sim |
| `cidade` | `VARCHAR` | Sim |
| `uf` | `VARCHAR` | Sim |

### `pagamentos.parquet`

| Coluna | Tipo DuckDB | Aceita nulo |
| --- | --- | --- |
| `order_id` | `VARCHAR` | Não |
| `tipo_pagamento_predominante` | `VARCHAR` | Sim |
| `parcelas_tipo_predominante` | `INTEGER` | Sim |
| `qtd_transacoes` | `BIGINT` | Não |
| `qtd_metodos_distintos` | `BIGINT` | Não |
| `valor_total_pago` | `DECIMAL(18,2)` | Sim |

### `avaliacoes.parquet`

| Coluna | Tipo DuckDB | Aceita nulo |
| --- | --- | --- |
| `order_id` | `VARCHAR` | Não |
| `review_id` | `VARCHAR` | Não |
| `titulo_review` | `VARCHAR` | Sim |
| `mensagem_review` | `VARCHAR` | Sim |
| `nota_review` | `INTEGER` | Sim |
| `ts_criacao_review` | `TIMESTAMP` | Sim |
| `ts_resposta_review` | `TIMESTAMP` | Sim |
| `flag_avaliacao_duplicada_pedido` | `BOOLEAN` | Não |

### `geografia_integrada.parquet`

| Coluna | Tipo DuckDB | Aceita nulo |
| --- | --- | --- |
| `cod_ibge` | `VARCHAR` | Não |
| `municipio` | `VARCHAR` | Não |
| `municipio_normalizado` | `VARCHAR` | Não |
| `uf` | `VARCHAR` | Não |
| `nome_uf` | `VARCHAR` | Sim |
| `regiao` | `VARCHAR` | Sim |
| `porte_municipio` | `VARCHAR` | Não |
| `populacao_estimada` | `BIGINT` | Sim |
| `ano_referencia_indicadores` | `INTEGER` | Sim |
| `pib_per_capita` | `DECIMAL(18,2)` | Sim |
| `latitude_representativa` | `DOUBLE` | Sim |
| `longitude_representativa` | `DOUBLE` | Sim |

### `distancias_itens.parquet`

| Coluna | Tipo DuckDB | Aceita nulo |
| --- | --- | --- |
| `order_id` | `VARCHAR` | Não |
| `motivo_distancia_ausente` | `VARCHAR` | Sim |
| `order_item_id` | `INTEGER` | Não |
| `distancia_km` | `DOUBLE` | Sim |
| `flag_distancia_calculada` | `BOOLEAN` | Não |

### `clientes_municipios.parquet`

| Coluna | Tipo DuckDB | Aceita nulo |
| --- | --- | --- |
| `customer_id` | `VARCHAR` | Não |
| `cod_ibge` | `VARCHAR` | Sim |
| `metodo_match` | `VARCHAR` | Não |
| `cidade_original` | `VARCHAR` | Sim |
| `cidade_normalizada` | `VARCHAR` | Sim |
| `uf` | `VARCHAR` | Sim |
| `motivo_nao_resolvido` | `VARCHAR` | Sim |
| `distancia_match_km` | `DOUBLE` | Sim |
| `latitude_cliente` | `DOUBLE` | Sim |
| `longitude_cliente` | `DOUBLE` | Sim |

### `vendedores_municipios.parquet`

| Coluna | Tipo DuckDB | Aceita nulo |
| --- | --- | --- |
| `seller_id` | `VARCHAR` | Não |
| `cod_ibge` | `VARCHAR` | Sim |
| `metodo_match` | `VARCHAR` | Não |
| `cidade_original` | `VARCHAR` | Sim |
| `cidade_normalizada` | `VARCHAR` | Sim |
| `uf` | `VARCHAR` | Sim |
| `motivo_nao_resolvido` | `VARCHAR` | Sim |
| `distancia_match_km` | `DOUBLE` | Sim |
| `latitude_vendedor` | `DOUBLE` | Sim |
| `longitude_vendedor` | `DOUBLE` | Sim |

## 4. Tradução explícita na Gold

| Origem Silver | Destino / uso Gold |
| --- | --- |
| `itens_pedido.item_pedido_id` | `fato_item_pedido.order_item_id`; juntar com `distancias_itens.order_item_id` e `order_id` |
| `itens_pedido.preco_produto` | `valor_produto` |
| `itens_pedido.flag_frete_outlier` | `flag_outlier_frete`, se exposta na fato |
| `pedidos.ts_compra`, `ts_entrega_cliente` | Datas para resolver as SKs de tempo de compra e entrega |
| `pedidos.status_pedido` | `flag_entregue = (status_pedido = 'delivered')`, se necessária |
| `produtos.categoria_produto`, `categoria_produto_ingles` | `dim_produto.categoria_pt`, `categoria_en` |
| `produtos.peso_g` | `dim_produto.peso_gramas` |
| `produtos.flag_peso_imputado`, `flag_dimensoes_imputadas` | `peso_imputado`, `dimensoes_imputadas` |
| `pagamentos.parcelas_tipo_predominante` | `dim_pagamento.quantidade_parcelas` |
| `pagamentos.tipo_pagamento_predominante` | `dim_pagamento.tipo_pagamento` |
| `pagamentos.valor_total_pago` | Auditoria por pedido; nunca somar na fato de itens |
| `avaliacoes.nota_review` | `nota_avaliacao`, com média na fato de pedidos |
| `clientes.customer_unique_id` | Chave natural de `dim_cliente` |
| `clientes_municipios.cod_ibge` | Geografia do cadastro daquele pedido, não localização única da pessoa |

Os nomes do destino acima não são exigências de renomeação dos Parquets.
`volume_cm3` é derivado na Gold por comprimento × altura × largura; qualquer fator nulo produz nulo.
`faixa_peso` e `faixa_parcelas` são classificações da Gold, não campos faltantes da Silver. Os limites implementados estão registrados na seção 16 do modelo dimensional.
`qtd_fotos`, `flag_tem_comentario`, `quantidade_avaliacoes` e frete winsorizado não são entradas obrigatórias. A Silver preserva os textos e a flag de múltiplas avaliações; uma contagem exata não deve ser inferida dessa flag.

## 5. Regras consolidadas

### Pedidos, valores e frete

- Preservar todos os pedidos, inclusive sem itens. Somar itens por pedido antes de combinar com pagamentos e avaliações.
- `valor_total_item = preco_produto + valor_frete`. Não substituir componentes ausentes por zero.
- Prazo: `date_diff('day', ts_compra, ts_entrega_cliente)` somente para entregues com datas suficientes. Atraso usa entrega real menos estimativa; negativo significa antecipação. `flag_atraso` é nula quando o atraso não é calculável.
- `flag_entrega_ausente` identifica especificamente status `delivered` sem data real de entrega.
- Outlier de frete: acima de Q3 + 1,5 × (Q3 − Q1), com quartis contínuos calculados sobre todos os itens da execução. Preservar o frete original; não aplicar winsorização. Frete nulo gera flag nula.
- Faixas de preço: `baixo` até 39,90; `medio_baixo` até 74,99; `medio_alto` até 134,90; `alto` acima; preço nulo é `nao_informado`. Os limites são fixos, não recalculados por execução.

### Pagamentos e avaliações

- Pagamento predominante: maior soma por tipo no pedido; empate por nome do tipo em ordem alfabética ascendente. Parcelas: máximo dentro do tipo vencedor.
- Pagamentos são consolidados antes de joins. A ausência de pagamento não elimina o pedido.
- Avaliação: maior data de criação, depois maior data de resposta, depois maior `review_id`; datas nulas ficam por último. Uma avaliação por pedido; nota válida de 1 a 5, nulo preservado.
- Título e mensagem permanecem na Silver, sem obrigação de levá-los ao modelo dimensional. Demais avaliações permanecem na Bronze.

### Produtos

- Categoria ausente: `nao_informado`. Tradução ausente: categoria em português, com flag para categoria conhecida sem tradução.
- Imputação por mediana da categoria exige pelo menos cinco observações não nulas da medida. Sem suporte suficiente, preservar nulo.
- Flags de imputação indicam substituição efetivamente realizada; nulo sem suporte não é imputação.

### Geografia e distâncias

- Preservar todo o cadastro IBGE obtido na execução; não fixar cardinalidade em 5.570. Indicadores são o retrato de 2017, unidos por `cod_ibge`, sem inventar dados para município ausente no SIDRA.
- `porte_municipio`: `Pequeno` para população < 50.000; `Médio` de 50.000 a 500.000; `Grande` acima; `Não informado` se nula. Estes são os literais físicos; a Gold pode padronizar apresentação explicitamente.
- Match: nome normalizado + UF (incluindo segunda tentativa sem espaços, apenas se chave única), depois de-para manual, depois município mais próximo na mesma UF até 50 km. Correções manuais justificadas podem corrigir UF incorreta da origem.
- Vocabulário oficial nos dois arquivos `*_municipios`: `exato`, `manual`, `geografico`, `nao_resolvido`. Internamente e nos arquivos auxiliares, `de_para` corresponde a `manual`.
- O fallback ordena por distância e, em empate, por código IBGE. Não existe margem implementada de rejeição entre primeiro e segundo candidato; proximidade é estimativa, não prova de pertencimento municipal. Chaves textuais ambíguas não são aceitas no match exato.
- Pontos municipais são derivados somente de matches exatos. Casos não resolvidos mantêm `cod_ibge` nulo e motivo; a Gold usa membro técnico SK 0.
- A distância analítica oficial é `distancias_itens.distancia_km`, Haversine entre medianas dos CEPs do vendedor e cliente. Não depende de resolver o município. Coordenada ausente gera distância nula e motivo.
- Pontos elegíveis para medianas ficam na caixa aproximada lat [-34,6], lon [-75,-33]. Isso não equivale a teste preciso de fronteira territorial.

## 6. Auxiliares e compatibilidade

`municipios.parquet`, `geolocalizacao_pontos.parquet` e `geolocalizacao_cep.parquet` são insumos/artefatos auxiliares da integração.
`municipios_cliente.parquet` e `municipios_vendedor.parquet` permanecem para auditoria das verificações existentes; a Gold usa exclusivamente `clientes_municipios` e `vendedores_municipios`.
`distancias_vendedor_cliente.parquet` é uma medida auxiliar entre pontos municipais, com grão por par. Não é equivalente à distância por CEP e não deve substituir a distância oficial por item.

A integração também gera `municipios_nao_resolvidos.csv` e `qualidade_integracao_municipios.json`. São evidências de qualidade, não fontes alternativas do dashboard. Se o dashboard exibir cobertura de integração, a Gold deverá disponibilizar os dados necessários no DW.

## 7. Verificação e migração

Executar `python -m src.run_pipeline --ate validacao` para regenerar Bronze, Silver e integração e validar a interface. Consumidores antigos devem adotar os onze nomes da seção 2 e os aliases da seção 4; não criar cópias de pagamentos/avaliações com os nomes antigos propostos.
Os arquivos auxiliares existentes continuam sendo produzidos nesta revisão para manter as verificações de integração. Eles não ampliam o contrato oficial de entrada.
A Gold implementada em `src/gold/dimensional.py` valida esta interface antes de cada carga. Ver `docs/gold.md` para resultados e execução.
