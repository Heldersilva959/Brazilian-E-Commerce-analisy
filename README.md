# Data Warehouse de e-commerce brasileiro

Trabalho acadêmico de Data Warehouse / BI: integração de vendas, logística e satisfação do cliente do Olist com municípios e indicadores socioeconômicos do IBGE.

O projeto prioriza SQL legível, decisões de negócio documentadas e execução local. Não inclui dashboard, nuvem, Docker, Spark ou Airflow.

## Estado atual

Implementação com revisão ao final de cada etapa:

1. **Bronze: pronta e executada.** Onze tabelas, 1.562.064 linhas, contagem conferida arquivo por arquivo. Ver [`docs/membro1_bronze.md`](docs/membro1_bronze.md).
2. **Silver: pronta e executada.** Dez tabelas geradas a partir da bronze real, 1.570.435 linhas. Ver [`docs/silver_contrato.md`](docs/silver_contrato.md).
3. **Integração de municípios: pronta e executada.** Match exato, fallback geográfico e de-para manual; 99,91% dos clientes e 99,94% dos vendedores resolvidos. Ver [`docs/relatorio_match.md`](docs/relatorio_match.md).
4. **Validação de bronze e silver: pronta e executada.** 121 testes a cada execução. Ver [`docs/validacao_bronze_silver.md`](docs/validacao_bronze_silver.md).
5. Gold: dimensões e fatos materializadas. Em desenvolvimento.
6. Qualidade da gold: validações e relatório. Em desenvolvimento.

O orquestrador (`src/run_pipeline.py`) já roda de ponta a ponta: as etapas ainda não escritas são anunciadas e puladas, e o pipeline segue. O relatório de qualidade da gold ainda não foi calculado.

O levantamento das fontes brutas — contagens, colunas, tipos, vazios, encoding e `sha256` de cada arquivo — está em [`docs/inventario_fontes.md`](docs/inventario_fontes.md).

## Ambiente

Python 3.11 ou superior. Quatro dependências diretas, com versão fixada em `requirements.txt`:

- **DuckDB** (`1.5.5`): transformações SQL da silver e da gold, e o banco dimensional.
- **pandas** (`2.2.3`): leitura dos CSV na bronze e manipulações tabulares.
- **PyArrow** (`18.0.0`): escrita dos Parquet com esquema declarado.
- **requests** (`2.32.3`): única dependência de rede, usada na API de localidades do IBGE.

No PowerShell, a partir da raiz do repositório:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Execução

```powershell
python -m src.run_pipeline                    # bronze -> silver -> integracao -> validacao -> gold -> qualidade
python -m src.run_pipeline --etapa bronze     # só uma etapa
python -m src.run_pipeline --ate validacao    # da primeira etapa até essa
```

O log traz, por etapa, horário de início, duração, tabelas geradas e contagem de linhas de entrada e de saída. Etapa cujo módulo ainda não foi escrito é anunciada e pulada; erro dentro de uma etapa que existe derruba a execução, com o log dizendo qual etapa quebrou.

Não são usados dados sintéticos ou mocks. Arquivo obrigatório ausente interrompe a execução informando a tabela afetada, o caminho esperado e onde obter o arquivo.

## Estrutura

```text
.
├── src/
│   ├── bronze/
│   ├── silver/
│   ├── gold/
│   └── utils/
├── data/
│   ├── raw/
│   │   ├── olist/
│   │   ├── ibge/
│   │   └── socioeconomico/
│   ├── bronze/
│   ├── silver/
│   └── gold/
├── docs/
├── de_para_municipios.csv
├── requirements.txt
└── README.md
```

Já existem `src/run_pipeline.py`, `src/bronze/ingest.py`, `src/silver/transform.py`, `src/silver/integracao_municipios.py`, `src/utils/normalizacao.py` e `src/qualidade/validar_camadas.py`. Faltam `src/gold/dimensional.py` e `src/gold/qualidade.py`, que entram na etapa do membro 4.

`data/raw/` é versionado no Git; `data/bronze/`, `data/silver/` e `data/gold/` não, porque são reconstruídos a cada execução (contrato §1).

## Fontes e preparação dos arquivos

### 1. Olist — download manual

Baixar o [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) e colocar estes nove arquivos em `data/raw/olist/`:

```text
olist_orders_dataset.csv
olist_order_items_dataset.csv
olist_products_dataset.csv
olist_customers_dataset.csv
olist_sellers_dataset.csv
olist_order_payments_dataset.csv
olist_order_reviews_dataset.csv
olist_geolocation_dataset.csv
product_category_name_translation.csv
```

O projeto não fará download do Kaggle por script.

### 2. IBGE Localidades — JSON com cache

Endpoint: [municípios do IBGE](https://servicodados.ibge.gov.br/api/v1/localidades/municipios).

A bronze reutiliza `data/raw/ibge/municipios.json` enquanto ele tiver menos de 30 dias; passou disso, ou não existe, ela baixa e grava a resposta byte a byte, sem reformatar. A ausência desse cache é a única ausência de fonte que permite obtenção automática; falha na API interrompe a execução. O `sha256` do JSON vai para o log a cada execução, para o grupo conferir que está todo mundo com a mesma versão do cadastro.

Nada pressupõe contagem fixa de municípios nem presença universal das antigas microrregiões e mesorregiões — e com razão: o cadastro atual tem **5.571** municípios, um a mais que o recorte de 2017, e **Boa Esperança do Norte (5101837, MT)** não tem microrregião nem mesorregião. UF e região devem ser lidas pelo ramo `regiao-imediata`, que está preenchido em todos.

### 3. SIDRA — retrato socioeconômico de 2017

Preparar `data/raw/socioeconomico/indicadores_municipais.csv` com este cabeçalho exato:

```csv
cod_ibge,ano_referencia,populacao_estimada,pib_per_capita
```

| Coluna | Contrato |
| --- | --- |
| `cod_ibge` | Código municipal de sete dígitos, lido como texto |
| `ano_referencia` | Inteiro 2017 |
| `populacao_estimada` | Quantidade inteira de habitantes |
| `pib_per_capita` | Reais por habitante; ponto como separador decimal |

Regras:

- UTF-8, vírgula como delimitador e uma única linha de cabeçalho.
- Uma linha por município, sem códigos duplicados; código e ano são obrigatórios.
- Sem separador de milhar, símbolo monetário, totais estaduais, títulos ou rodapés.
- Indicadores ausentes ficam vazios; não substituir por zero.
- Selecionar todos os municípios e o ano de 2017 para ambos os indicadores.
- Não misturar PIB total, valores em milhares de reais e PIB per capita.

Referências: [população estimada, tabela 6579](https://sidra.ibge.gov.br/tabela/6579), variável 9324, e [PIB municipal, tabela 5938](https://sidra.ibge.gov.br/tabela/5938), variável 37, em Mil Reais. A tabela 5938 não publica PIB per capita — nenhuma tabela da pesquisa publica —, então o indicador é derivado do PIB dividido pela população do mesmo ano e convertido para reais por habitante.

As duas exportações e o cadastro de municípios são obtidos por `python src/utils/baixar_fontes_ibge.py`, que reutiliza o que já estiver em disco e grava um `.meta.json` com URL, data de obtenção e SHA-256 ao lado de cada original. Guardar as exportações originais em `data/raw/socioeconomico/originais/`; os filtros, unidades e ajustes estão documentados em [`docs/fontes_ibge_sidra.md`](docs/fontes_ibge_sidra.md). O pipeline consumirá o arquivo consolidado acima; os originais serão preservados para auditoria, sem serem concatenados automaticamente à entrada.

Os indicadores de 2017 serão atributos fixos da geografia para todo o período de vendas. Não permitirão concluir sobre evolução anual de população ou PIB.

## Integração de municípios

O IBGE Localidades é o cadastro canônico de códigos e nomes, mas não fornece coordenadas municipais. Foi aprovado manter somente os insumos previstos, usando pontos representativos estimados a partir do próprio Olist.

A ordem será:

1. **Normalização e match exato:** NFKD, remoção de acentos, minúsculas, remoção de pontuação e redução de espaços repetidos. A chave sempre inclui cidade normalizada e UF. Chaves ambíguas não serão aceitas automaticamente.
2. **Fallback geográfico:** agregar latitude e longitude por prefixo de CEP pela mediana. Estimar pontos representativos municipais apenas com coordenadas de localidades Olist que tiveram match exato com o IBGE. Buscar por Haversine o candidato da mesma UF. Esses pontos são aproximações do Olist, não sedes ou centroides oficiais; municípios sem evidência não terão ponto inventado. Matches do fallback não alimentarão novamente a referência.
3. **De-para manual:** resolver o resíduo por `de_para_municipios.csv`, versionado e inicialmente apenas com cabeçalho. Não há correspondências inventadas.

O fallback terá limite de distância e rejeição de ambiguidade. Os valores desses critérios serão definidos e documentados na etapa de integração, com inspeção dos dados reais. Coordenadas inválidas serão sinalizadas e excluídas do cálculo espacial, preservando seus registros de origem. Proximidade não comprova pertencimento ao município, especialmente nas fronteiras municipais.

Layout do de-para:

```csv
cidade_normalizada,uf,cod_ibge,justificativa
```

A UF deverá coincidir com a do município de destino. A chave cidade/UF deverá ser única. Cada preenchimento deverá ter justificativa verificável.

A integração atenderá clientes e vendedores. A taxa principal será a proporção de registros de clientes (`customer_id`) mapeados, com contagem por método e lista dos não resolvidos, impressas e persistidas. Não se promete antecipadamente uma taxa mínima. A cobertura dos indicadores socioeconômicos será medida separadamente.

## Arquitetura medalhão

### Bronze

Parquet com todos os campos de origem como texto, sem limpar valores nem renomear colunas. Quatro colunas de linhagem em cada tabela: `_fonte`, `_arquivo_origem`, `_data_ingestao` e `_linha_origem` (número do registro na origem, base 1). Nenhum filtro, nenhuma deduplicação: a contagem de saída é conferida contra a de entrada arquivo por arquivo, e divergência derruba a execução.

Os arquivos originais não são copiados para a bronze — `data/raw/` é versionado no Git, então já serve de referência para auditoria.

A data de ingestão é mantida enquanto o conteúdo da fonte permanecer igual: o `sha256` de cada origem fica em `data/bronze/_manifesto.json`, e a reexecução com fonte inalterada preserva o `_data_ingestao` anterior. Conferido: duas execuções seguidas produzem os onze Parquet byte a byte idênticos.

Detalhes de implementação, nomes de coluna do JSON do IBGE e decisões de leitura em [`docs/membro1_bronze.md`](docs/membro1_bronze.md).

### Silver

Parquet com nomes padronizados em português, timestamps e números tipados. Valores monetários usarão `DECIMAL`.

- Categoria ausente: `nao_informado`, preservando os produtos e suas vendas.
- Entrega ausente: manter o nulo e uma flag; métricas de prazo apenas para entregues com datas válidas. Ausência de prazo ou atraso não significa zero.
- Peso e dimensões ausentes: mediana da categoria, com identificação da imputação. Se a categoria não tiver valores suficientes, manter nulo e registrar a ocorrência.
- Geolocalização: mediana por prefixo de CEP, preservando zeros à esquerda do prefixo.
- Avaliações: manter a mais recente por data de criação, com desempate determinístico; preservar as demais na bronze.
- Pagamentos: agregar por pedido antes dos joins. Tipo predominante é aquele com maior valor agregado; parcelas são o máximo observado nesse tipo. Empates terão regra estável documentada.
- Frete: sinalizar outliers sem apagar valores. Não haverá winsorização por padrão.
- Derivadas: `dias_ate_entrega`, `dias_atraso`, `flag_atraso`, `distancia_km`, `ano_mes` e `faixa_preco`. Distância é geodésica aproximada entre vendedor e cliente, não distância rodoviária.

Limiares de faixas de preço, peso, parcelas e porte municipal, assim como a regra de outliers, serão explicitados na implementação da respectiva etapa.

### Validação de bronze e silver

`src/qualidade/validar_camadas.py` roda depois da integração e antes da gold, para que as fatos só sejam montadas sobre camadas conferidas. São cinco famílias de teste: `BRZ-*` (cópia literal, linhagem, contagem recontada contra `data/raw/` e `sha256` da origem), `SLV-*` (PK, órfão, grão preservado contra a bronze, reconciliação monetária e regra de negócio), `INT-*` (método de match, raio do fallback, unicidade do mapeamento e cobertura socioeconômica), `CTR-*` (divergências entre a silver real e o contrato de dados) e `REP-*` (reprodutibilidade).

O módulo importa as constantes das camadas que valida — `BRONZE_ESPERADA`, a caixa delimitadora do Brasil, `RAIO_ACEITE_KM`, `contar_registros`, `sha256_arquivo` — em vez de repetir os valores, para que a validação não possa divergir em silêncio da regra validada.

Classificação e desfecho seguem [`docs/plano_qualidade.md`](docs/plano_qualidade.md) §3 e §20: `REPROVADO` derruba o pipeline, mas só depois de o relatório estar gravado. As famílias `CTR-*` apenas reportam — renomear coluna agora quebraria a integração, que já consome os nomes atuais; a decisão é do grupo, numa revisão de contrato.

Saídas: [`docs/validacao_bronze_silver.md`](docs/validacao_bronze_silver.md) e `data/silver/validacao_bronze_silver.json`, este para a gold consumir sem reparsear markdown. Ambos são recriados a cada execução.

### Gold

Banco local `data/gold/dw.duckdb`, com surrogate keys sequenciais, ordenação determinística pelas chaves naturais e índices nas FKs.

| Tabela | Grão ou chave natural |
| --- | --- |
| `fato_item_pedido` | Um item: pedido + identificador do item |
| `fato_pedido` | Um pedido, inclusive pedidos sem itens |
| `dim_tempo` | Uma data; mínimo de 2016-01-01 a 2018-12-31 |
| `dim_produto` | `product_id` |
| `dim_cliente` | `customer_unique_id` |
| `dim_vendedor` | `seller_id` |
| `dim_geografia` | Código IBGE, com indicadores de 2017 |
| `dim_pagamento` | Combinação de tipo predominante e parcelas |

A fato de itens terá `sk_tempo_compra`, `sk_tempo_entrega`, `sk_produto`, `sk_cliente`, `sk_vendedor`, `sk_geo_cliente` e `sk_pagamento`; pedido como dimensão degenerada; medidas de produto, frete, total do item, prazo, atraso, distância e avaliação. O identificador do item será preservado para verificar seu grão.

A geografia da fato será a do endereço daquele pedido: uma pessoa pode comprar em endereços diferentes. A dimensão cliente não substituirá esse endereço por uma localização única atual.

A dimensão tempo será usada nos papéis compra e entrega e ampliada se houver datas reais fora do intervalo previsto. Membros técnicos de ausência permitirão FKs válidas sem inventar clientes, produtos, datas ou municípios reais.

Todas as dimensões usarão SCD Tipo 1, sem histórico de versões. Tipo 2 seria aplicável a produtos se existisse histórico de mudanças; o dataset é um snapshot.

## Regras de métricas e granularidade

- O valor total do item é preço + frete. Valores de pagamentos não serão repetidos e somados no grão de item.
- A avaliação é por pedido: sua presença na fato de itens serve a análises específicas, mas médias de satisfação serão calculadas na `fato_pedido`.
- Prazo médio e percentual de atraso também serão calculados por pedido, evitando ponderação pelo número de itens.
- Recompra usará a identidade `customer_unique_id` e pedidos distintos.
- O termo faturamento deverá explicitar os status incluídos e se inclui frete. A reconciliação técnica comparará o mesmo conjunto de itens e as mesmas medidas entre silver e gold.

## Qualidade e reprodutibilidade

Ao final, `data/gold/qualidade.md` deverá apresentar:

- Contagem de órfãos em cada FK, esperada igual a zero.
- Unicidade de PKs e do grão das duas fatos.
- Reconciliação de valores monetários da gold com a silver.
- Taxa de match municipal, métodos utilizados e casos não resolvidos.
- Contagens por tabela em cada camada.

O pipeline usará `logging` com entradas e saídas por etapa. Erros não serão escondidos com capturas genéricas. Nenhuma linha com nulo será descartada silenciosamente.

A idempotência será verificada com as mesmas fontes, cache, de-para e dependências: duas execuções deverão manter conteúdos, chaves e totais iguais, sem acumular duplicatas. Isso não exige que o arquivo físico do banco DuckDB tenha bytes idênticos.

As saídas reais, amostras e limitações são apresentadas após cada camada implementada. As da bronze estão em [`docs/membro1_bronze.md`](docs/membro1_bronze.md); a próxima etapa é a silver.
