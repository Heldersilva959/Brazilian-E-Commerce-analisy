# Fontes do IBGE e do SIDRA

Registro do que foi obtido, com quais filtros e unidades, e de quais ajustes
foram necessários para produzir `data/raw/socioeconomico/indicadores_municipais.csv`.

Obtenção: 2026-09-15 (UTC), pelo script `src/utils/baixar_fontes_ibge.py`, que
usa apenas a biblioteca padrão do Python. O script reutiliza os arquivos já
gravados e só acessa a rede quando eles não existem, de modo que reexecutá-lo
não altera o que está em disco. Cada arquivo original tem um `.meta.json` ao
lado com URL, data de obtenção, tamanho e SHA-256.

Os arquivos ficam versionados junto com as bases do Olist, no mesmo commit em
que entraram. Quem preferir reproduzi-los do zero pode apagá-los e rodar o
script de novo; os `.meta.json` permitem conferir se o conteúdo obtido é o
mesmo.

## 1. IBGE Localidades

| Item | Valor |
| --- | --- |
| Endpoint | `https://servicodados.ibge.gov.br/api/v1/localidades/municipios` |
| Arquivo | `data/raw/ibge/municipios.json` |
| Tamanho | 2.470.036 bytes |
| SHA-256 | `86ecdccd…` (íntegro em `municipios.json.meta.json`) |
| Registros | 5.571 municípios |

A resposta foi gravada byte a byte, sem reformatação. Cada município traz `id`,
`nome`, `microrregiao` (com `mesorregiao` e UF aninhadas) e `regiao-imediata`
(com `regiao-intermediaria` e UF aninhadas). UF e região podem ser lidas por
qualquer um dos dois ramos.

Observações relevantes para a integração:

- A hierarquia antiga não é universal: **Boa Esperança do Norte (5101837, MT)**
  não tem `microrregiao`, apenas `regiao-imediata`. Código que assumir
  micro/mesorregião sempre presente quebra nesse registro.
- O cadastro é o atual (5.571 municípios), não o recorte de 2017. Boa Esperança
  do Norte foi instalada depois de 2017 e por isso não tem indicadores daquele
  ano — ver seção 3.

## 2. SIDRA — insumos de 2017

Ambas as consultas usaram nível territorial **N6 (municípios)**, seleção de
todos os municípios e período **2017**.

| Tabela | Variável | Unidade | Arquivo original | Registros |
| --- | --- | --- | --- | --- |
| [6579](https://sidra.ibge.gov.br/tabela/6579) | 9324 — População residente estimada | Pessoas | `originais/sidra_6579_populacao_estimada_2017.json` | 5.571 |
| [5938](https://sidra.ibge.gov.br/tabela/5938) | 37 — PIB a preços correntes | **Mil Reais** | `originais/sidra_5938_pib_2017.json` | 5.570 |

As respostas do `apisidra` foram gravadas sem alteração; são elas as
"exportações originais" previstas no README. A primeira linha de cada resposta
traz rótulos de coluna, não dados, e é descartada na consolidação.

Conferência: a soma da população estimada dá **207.660.929 habitantes**, igual
ao total divulgado pelo IBGE para 2017.

### PIB per capita não existe na tabela 5938

O README previa selecionar o indicador "PIB per capita em reais" na tabela 5938.
Esse indicador **não existe ali**: as 46 variáveis da tabela são o PIB, os
impostos e o valor adicionado bruto (todos em Mil Reais) e participações
percentuais. Nenhuma das quatro tabelas da pesquisa "Produto Interno Bruto dos
Municípios" no SIDRA (21, 5938, 5939 e 599) publica PIB per capita.

Ajuste adotado: derivar o indicador como

```text
pib_per_capita = PIB (Mil Reais) × 1000 ÷ população estimada do mesmo ano
```

que é a própria definição usada pelo IBGE. A conversão de Mil Reais para Reais
é o único ajuste de unidade feito; nenhum valor de PIB total entra no CSV
consolidado, evitando a mistura de grandezas que o README proíbe.

Limitação: o resultado pode divergir na casa dos centavos do PIB per capita
publicado pelo IBGE, que usa a estimativa populacional vigente na data de
divulgação do PIB. Para São Paulo (3550308) a derivação dá R$ 57.731,63. O
indicador serve para comparação relativa entre municípios, não como valor
oficial citável.

## 3. Arquivo consolidado

`data/raw/socioeconomico/indicadores_municipais.csv`, UTF-8, vírgula como
delimitador, uma linha de cabeçalho, sem separador de milhar nem símbolo
monetário, ponto como separador decimal:

```csv
cod_ibge,ano_referencia,populacao_estimada,pib_per_capita
```

- 5.571 linhas de dados, uma por município, sem códigos duplicados.
- Todos os códigos têm sete dígitos e devem ser lidos como texto.
- `ano_referencia` é 2017 em todas as linhas.
- Ordenação por `cod_ibge`, o que torna a saída estável entre execuções.

Ausências, deixadas vazias e nunca substituídas por zero:

| Município | Faltando | Motivo |
| --- | --- | --- |
| Boa Esperança do Norte (5101837, MT) | população e PIB per capita | Município criado depois de 2017; não aparece no PIB de 2017 e não tem valor de população naquele ano |

Os demais 5.570 municípios têm população e PIB per capita preenchidos. A
dispersão do PIB per capita derivado vai de R$ 3.289,52 a R$ 346.739,34, com
mediana de R$ 16.615,99.

Como o README determina, os originais ficam preservados em
`data/raw/socioeconomico/originais/` para auditoria e não são concatenados
automaticamente à entrada do pipeline: este CSV é a única entrada consumida.
