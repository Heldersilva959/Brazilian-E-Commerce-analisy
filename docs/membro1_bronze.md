# Camada bronze e orquestração — membro 1

Documentação da minha parte: `src/bronze/ingest.py` e `src/run_pipeline.py`.
Complementa o contrato de dados (`contratos_dados.md`, seção 3) com o que foi
decidido na implementação e com os números da execução real.

O levantamento das fontes que embasou estas decisões está em
[`inventario_fontes.md`](inventario_fontes.md).

---

## 1. O que a bronze faz e o que ela não faz

Cópia literal de `data/raw/` para Parquet. **Faz**: lê tudo como texto, numera
as linhas, marca a procedência, grava em snappy e confere a contagem. **Não
faz**: cast, parse de data, conversão numérica, filtro, deduplicação,
normalização de texto, troca de `''` por `NULL`, imputação. Tudo isso é da
silver.

A consequência prática é que a bronze não tem regra de negócio nenhuma. Se um
valor está errado na origem, ele chega errado na bronze — de propósito. É o que
permite auditar depois de onde veio cada distorção.

## 2. Como executar

```bash
pip install -r requirements.txt

python -m src.run_pipeline --etapa bronze   # só a bronze
python -m src.bronze.ingest                 # idem, sem passar pelo orquestrador
```

A primeira execução leva cerca de 6 segundos e grava 11 arquivos em
`data/bronze/`, somando 1.562.064 linhas. Os Parquet e o `_manifesto.json`
ficam fora do Git (contrato §1, versão 1.1).

## 3. As onze tabelas

Contagens da execução de 2026-09-14. A coluna "colunas" não inclui as quatro de
linhagem, que existem em todas.

| Parquet em `data/bronze/` | Origem | `_fonte` | Linhas | Colunas |
|---|---|---|---|---|
| `olist_pedidos.parquet` | `olist_orders_dataset.csv` | `olist` | 99.441 | 8 |
| `olist_itens_pedido.parquet` | `olist_order_items_dataset.csv` | `olist` | 112.650 | 7 |
| `olist_produtos.parquet` | `olist_products_dataset.csv` | `olist` | 32.951 | 9 |
| `olist_clientes.parquet` | `olist_customers_dataset.csv` | `olist` | 99.441 | 5 |
| `olist_vendedores.parquet` | `olist_sellers_dataset.csv` | `olist` | 3.095 | 4 |
| `olist_pagamentos.parquet` | `olist_order_payments_dataset.csv` | `olist` | 103.886 | 5 |
| `olist_avaliacoes.parquet` | `olist_order_reviews_dataset.csv` | `olist` | 99.224 | 7 |
| `olist_geolocalizacao.parquet` | `olist_geolocation_dataset.csv` | `olist` | 1.000.163 | 5 |
| `olist_traducao_categoria.parquet` | `product_category_name_translation.csv` | `olist` | 71 | 2 |
| `socioeconomico_municipios.parquet` | `indicadores_municipais.csv` | `sidra` | 5.571 | 4 |
| `ibge_municipios.parquet` | API de localidades do IBGE | `ibge_api` | 5.571 | 22 |

Os nomes das colunas de dados são os da origem, sem renomear. A única exceção é
o IBGE, que não tem cabeçalho para copiar — ver seção 5.

**Divergência conhecida contra o contrato:** o IBGE tem 5.571 municípios e a
seção 3 do contrato prevê 5.570. O excedente é Boa Esperança do Norte
(5101837, MT), instalada depois de 2017. Quem monta a `dim_geografia`
(cardinalidade 5.570 na seção 6.2) precisa decidir se ela entra.

## 4. Colunas de linhagem

| Coluna | Tipo no Parquet | Conteúdo |
|---|---|---|
| `_fonte` | `string` | `olist`, `sidra` ou `ibge_api` |
| `_arquivo_origem` | `string` | Nome do arquivo; para o IBGE, a URL do endpoint |
| `_data_ingestao` | `timestamp[us]` | Momento da ingestão, estável enquanto a fonte não mudar |
| `_linha_origem` | `int64` | Número do registro na origem, base 1 |

**`_linha_origem` conta registros, não linhas físicas.** Em
`olist_order_reviews_dataset.csv` os dois números não batem: são 104.720 linhas
no arquivo para 99.224 registros, porque 3.852 comentários têm quebra de linha
dentro do campo. Numerar por linha física daria um valor que não corresponde a
nenhum registro e que muda se alguém reabrir o CSV num editor.

## 5. Nomes das colunas do IBGE

A resposta da API é aninhada e não tem cabeçalho, então o nome da coluna é o
caminho do campo no JSON, com `_` no lugar do ponto e do hífen, tudo em
minúsculas — `microrregiao.mesorregiao.UF.sigla` vira
`microrregiao_mesorregiao_uf_sigla`. São 22 colunas:

```
id                                                   nome
microrregiao_id                                      microrregiao_nome
microrregiao_mesorregiao_id                          microrregiao_mesorregiao_nome
microrregiao_mesorregiao_uf_id                       microrregiao_mesorregiao_uf_sigla
microrregiao_mesorregiao_uf_nome                     microrregiao_mesorregiao_uf_regiao_id
microrregiao_mesorregiao_uf_regiao_sigla             microrregiao_mesorregiao_uf_regiao_nome
regiao_imediata_id                                   regiao_imediata_nome
regiao_imediata_regiao_intermediaria_id              regiao_imediata_regiao_intermediaria_nome
regiao_imediata_regiao_intermediaria_uf_id           regiao_imediata_regiao_intermediaria_uf_sigla
regiao_imediata_regiao_intermediaria_uf_nome         regiao_imediata_regiao_intermediaria_uf_regiao_id
regiao_imediata_regiao_intermediaria_uf_regiao_sigla regiao_imediata_regiao_intermediaria_uf_regiao_nome
```

Mapeamento para a `silver/municipios.parquet` (contrato §4.9):

| Coluna da silver | Coluna da bronze |
|---|---|
| `cod_ibge` | `id` |
| `municipio` | `nome` |
| `uf` | `regiao_imediata_regiao_intermediaria_uf_sigla` |
| `regiao` | `regiao_imediata_regiao_intermediaria_uf_regiao_nome` |
| `mesorregiao` | `microrregiao_mesorregiao_nome` |
| `microrregiao` | `microrregiao_nome` |

**Leia UF e região pelo ramo `regiao_imediata`, não pelo `microrregiao`.** O
ramo antigo está vazio em Boa Esperança do Norte; o novo está preenchido nos
5.571 municípios. As dez colunas do ramo `microrregiao` desse município saem
como `''`.

## 6. Decisões de leitura

Cada uma resolve um problema medido nos arquivos, não uma precaução genérica.

**`keep_default_na=False` e `na_filter=False` no pandas.** Sem isso, todo campo
vazio vira `NaN` — inclusive campo vazio entre aspas, como os 2.965 de
`order_delivered_customer_date`. A bronze entregaria `NULL` onde o contrato §2
manda entregar `''`. Varri as onze fontes: nenhuma usa `NA`, `null`, `nan` ou
`None` como valor de verdade, então desligar a conversão não perde informação.
Resultado: **zero nulos em coluna de dado nas onze tabelas**.

**`encoding='utf-8-sig'`.** `product_category_name_translation.csv` começa com
BOM. Lido como `utf-8` puro, a primeira coluna passa a se chamar
`﻿product_category_name` e o join da silver §4.3 devolve vazio sem erro.
Nos demais arquivos, que não têm BOM, o `-sig` não muda nada.

**Esquema do Parquet declarado, não inferido.** Toda coluna de dado é
`pa.string()` por construção. Se deixasse o pyarrow inferir, uma coluna cujos
valores todos parecem número viraria `int64` — exatamente o que a bronze não
pode fazer.

**Contagem conferida por dois caminhos independentes.** O módulo `csv` conta os
registros da origem, e o número de linhas gravadas é lido do metadado do
Parquet. Divergência levanta `ContagemDivergenteError` e derruba a execução; não
é aviso no log.

## 7. Idempotência

`_data_ingestao` só avança quando o conteúdo da fonte muda. O manifesto
`data/bronze/_manifesto.json` guarda, por tabela, o `sha256` da origem, a data
da ingestão e a contagem:

```json
"olist_pedidos": {
  "arquivo_origem": "olist_orders_dataset.csv",
  "caminho_origem": "olist/olist_orders_dataset.csv",
  "sha256": "1dca8c9a7a8d34f0a8d0f7c272616d582e7f29d67a8c21ddd903152bf4ee6441",
  "data_ingestao": "2026-09-14T22:52:56",
  "linhas": 99441
}
```

Além do hash bater, o Parquet precisa existir em disco — senão a data seria
herdada de uma execução cuja saída foi apagada.

Conferido: duas execuções seguidas produzem os **onze Parquet byte a byte
idênticos**, com os `_data_ingestao` preservados. Adulterando o hash guardado
no manifesto para simular uma fonte alterada, só a tabela afetada ganha
timestamp novo; as outras continuam com o antigo.

## 8. Cache da API do IBGE

`data/raw/ibge/municipios.json` é reusado enquanto tiver menos de 30 dias.
Passou disso, ou não existe, a bronze baixa de
`https://servicodados.ibge.gov.br/api/v1/localidades/municipios` e grava a
resposta **byte a byte, sem reformatar** — qualquer reindentação mudaria o
`sha256` que o grupo usa para conferir que está todo mundo com a mesma versão
do cadastro. O hash vai para o log a cada execução:

```
ibge: sha256 do JSON = 86ecdccdf97d72e7e5e46f0854cfcea8bacc28154cc1bc4ed0e6110e3a6c9c02
```

Conferido contra a API em 2026-09-14: o download devolve exatamente os mesmos
bytes que já estavam versionados no repositório.

## 9. Como a bronze falha

Sem `try/except` genérico e sem dado sintético. Três erros próprios:

| Exceção | Quando |
|---|---|
| `FonteAusenteError` | Arquivo de origem não está em `data/raw/`. A mensagem diz a tabela afetada, o arquivo, o caminho exato e onde obter. |
| `ContagemDivergenteError` | Saída com número de linhas diferente da origem. |
| `EstruturaInesperadaError` | JSON do IBGE com uma lista aninhada, forma que o achatamento não sabe tratar. Hoje não existe nenhuma. |

```
Fonte da bronze nao encontrada.
  Tabela afetada : olist_produtos
  Arquivo        : olist_products_dataset.csv
  Caminho exigido: ...\data\raw\olist\olist_products_dataset.csv
  Onde obter     : dataset 'Brazilian E-Commerce Public Dataset by Olist', no Kaggle
A bronze nao gera dado sintetico nem pula arquivo: coloque o arquivo no caminho
acima e execute de novo.
```

## 10. Orquestrador

`src/run_pipeline.py` executa bronze → silver → integracao → gold → qualidade.

```bash
python -m src.run_pipeline                  # tudo
python -m src.run_pipeline --etapa bronze   # só uma etapa
python -m src.run_pipeline --ate silver     # da primeira até essa
```

Cada etapa é um módulo do seu responsável, chamado por import:

| Etapa | Módulo | Responsável |
|---|---|---|
| bronze | `src.bronze.ingest` | membro 1 |
| silver | `src.silver.transform` | membro 2 |
| integracao | `src.silver.integracao_municipios` | membro 3 |
| gold | `src.gold.dimensional` | membro 4 |
| qualidade | `src.gold.qualidade` | membro 4 |

O orquestrador chama `executar()` do módulo ou, na falta dela, `main()`.

**Etapa cujo módulo ainda não existe é anunciada e pulada**, e o pipeline segue
— as quatro camadas estão sendo escritas em paralelo. A distinção é feita com
`importlib.util.find_spec` antes do import, justamente para não confundir "o
módulo ainda não foi escrito" com "o módulo existe e uma dependência dele
falta". O segundo caso é erro de verdade e derruba a execução, com o log
dizendo qual etapa quebrou.

O log registra, por etapa: horário de início, duração, tabelas geradas e
contagem de linhas. As contagens de **entrada e saída** aparecem quando a etapa
devolve itens com `tabela`, `linhas_entrada` e `linhas_saida` — é o que a
bronze devolve. Quem não devolver nada cai no inventário dos arquivos gravados,
que só enxerga a contagem de saída. É convenção, não exigência: nenhuma etapa
precisa mudar para funcionar no pipeline.

## 11. Pendências e avisos para o grupo

- **A silver espera outros nomes de arquivo.** `src/silver/transform.py` procura
  `pedidos.parquet`, `itens_pedido.parquet`, `traducao_categorias.parquet` —
  sem o prefixo `olist_` e com `categorias` no plural. O contrato §3 fixa
  `olist_pedidos.parquet`, `olist_itens_pedido.parquet` e
  `olist_traducao_categoria.parquet`, que é o que a bronze gera. Ajuste o
  dicionário `BRONZE_ESPERADA`.
- **`populacao_estimada`, não `populacao`.** O CSV socioeconômico usa o nome
  longo; a bronze preserva. O contrato §4.9 chama de `populacao` na silver, ou
  seja, o renomear acontece lá.
- **Código de município é texto de 7 posições nas duas fontes.** No JSON do
  IBGE ele é inteiro e no CSV é texto; na bronze os dois são texto. Comparar
  `int` com `str` no join devolve zero linhas sem erro nenhum.
