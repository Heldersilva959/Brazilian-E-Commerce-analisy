# Contrato de dados — DW E-commerce Brasileiro

**Versão:** 2.0
**Status:** consolidado nesta revisão Silver → Gold
**Revisão:** solicitada pelo usuário; não registra aprovação externa dos integrantes.

Este documento descreve a arquitetura e a Bronze. A interface Silver → Gold é definida exclusivamente em [contrato_entrada_gold.md](contrato_entrada_gold.md), com esquema executável em `src/silver/contrato_gold.py`. O modelo dimensional e os KPIs são definidos em seus documentos próprios. Esta revisão substitui as propostas conflitantes da versão 1.1.

---

## 1. Convenções gerais

| Assunto | Regra |
|---|---|
| Idioma | Tabelas, colunas e comentários em português, sem acento nos identificadores |
| Nomenclatura | `snake_case`; dimensões com prefixo `dim_`, fatos com `fato_` |
| Formato bronze/silver | Parquet, compressão snappy, um arquivo por tabela |
| Formato gold | DuckDB em `data/gold/dw.duckdb` |
| Valores monetários | `DECIMAL(18,2)` a partir da silver — nunca `FLOAT` |
| Distâncias | `DOUBLE`, em quilômetros, na interface Gold |
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

**Membro técnico nas dimensões** — toda dimensão tem uma linha com `sk = 0`, usada quando a fato não consegue resolver a FK. Atributos textuais recebem `'NAO INFORMADO'`, numéricos recebem `NULL`. Isso garante zero órfãos sem inventar dado.

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

## 4. Silver e integração

Entradas oficiais, nomes físicos, tipos, nulos e regras: [contrato Silver → Gold v2](contrato_entrada_gold.md).
Detalhes da transformação e evidências históricas: [Silver](silver_contrato.md).
Os arquivos auxiliares da integração não constituem uma segunda interface Gold.

## 5. Integração municipal

Consultar a seção de regras do contrato v2. A ordem é exato → manual → geográfico → não resolvido.
A distância analítica oficial é por item, entre coordenadas de CEP.

## 6. Gold

Consultar [modelo dimensional](modelo_dimensional.md). Duas fatos e seis dimensões; membro técnico com SK 0.
A Gold deverá validar a interface v2 antes de carregar, sem converter tipos incorretos silenciosamente.

## 7. KPIs

Consultar [kpis.md](kpis.md). Valor entregue inclui frete e apenas status `delivered`.
Satisfação e prazos usam a fato de pedidos; pagamentos não são somados no grão de item.

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

Versão 2.0: consolida a interface real da Silver, padroniza dinheiro em DECIMAL(18,2), adota SK 0 e remete modelos e KPIs aos documentos oficiais. A revisão foi solicitada pelo usuário; não implica aprovação externa dos demais integrantes.