# Relatório de match — integração geográfica

Gerado por `src/silver/integracao_municipios.py`. Não editar à mão:
os números são reescritos a cada execução.

## Taxa por método

### Clientes

| Método | Registros | Participação |
|---|---:|---:|
| exato | 98.853 | 99,41% |
| de_para (manual) | 0 | 0,00% |
| geografico | 502 | 0,50% |
| nao_resolvido | 86 | 0,09% |
| **total** | **99.441** | **100,00%** |

Taxa global de resolução: **99,91%**

### Vendedores

| Método | Registros | Participação |
|---|---:|---:|
| exato | 2.994 | 96,74% |
| de_para (manual) | 29 | 0,94% |
| geografico | 70 | 2,26% |
| nao_resolvido | 2 | 0,06% |
| **total** | **3.095** | **100,00%** |

Taxa global de resolução: **99,94%**

## De-para manual aplicado

| Cidade no Olist | UF | cod_ibge | Município oficial | Clientes | Vendedores | Evidência |
|---|---|---|---|---:|---:|---|
| curitiba | SP | 4106902 | Curitiba | 0 | 3 | UF divergente no cadastro Olist. Nome confere com Curitiba/PR, unico municipio com esse nome no pais; prefixo(s) de CEP 80240, 81020, 81560 a ate 7.3 km do centroide municipal. |
| belo horizonte | SP | 3106200 | Belo Horizonte | 0 | 2 | UF divergente no cadastro Olist. Nome confere com Belo Horizonte/MG, unico municipio com esse nome no pais; prefixo(s) de CEP 31160, 31570 a ate 11.2 km do centroide municipal. |
| caxias do sul | SP | 4305108 | Caxias do Sul | 0 | 2 | UF divergente no cadastro Olist. Nome confere com Caxias do Sul/RS, unico municipio com esse nome no pais; prefixo(s) de CEP 95055, 95076 a ate 4.1 km do centroide municipal. |
| itajai | SP | 4208203 | Itajaí | 0 | 2 | UF divergente no cadastro Olist. Nome confere com Itajaí/SC, unico municipio com esse nome no pais; prefixo(s) de CEP 88301 a ate 3.2 km do centroide municipal. |
| rio de janeiro | SP | 3304557 | Rio de Janeiro | 0 | 2 | UF divergente no cadastro Olist. Nome confere com Rio de Janeiro/RJ, unico municipio com esse nome no pais; prefixo(s) de CEP 21320, 22783 a ate 16.2 km do centroide municipal. |
| marechal candido rondon | PA | 4114609 | Marechal Cândido Rondon | 0 | 1 | UF divergente no cadastro Olist. Nome confere com Marechal Cândido Rondon/PR, unico municipio com esse nome no pais; prefixo(s) de CEP 85960 a ate 0.0 km do centroide municipal. |
| rio de janeiro | RN | 3304557 | Rio de Janeiro | 0 | 1 | UF divergente no cadastro Olist. Nome confere com Rio de Janeiro/RJ, unico municipio com esse nome no pais; prefixo(s) de CEP 21210 a ate 6.9 km do centroide municipal. |
| blumenau | SP | 4202404 | Blumenau | 0 | 1 | UF divergente no cadastro Olist. Nome confere com Blumenau/SC, unico municipio com esse nome no pais; prefixo(s) de CEP 89052 a ate 1.8 km do centroide municipal. |
| chapeco | SP | 4204202 | Chapecó | 0 | 1 | UF divergente no cadastro Olist. Nome confere com Chapecó/SC, unico municipio com esse nome no pais; prefixo(s) de CEP 89803 a ate 1.3 km do centroide municipal. |
| florianopolis | SP | 4205407 | Florianópolis | 0 | 1 | UF divergente no cadastro Olist. Nome confere com Florianópolis/SC, unico municipio com esse nome no pais; prefixo(s) de CEP 88075 a ate 6.1 km do centroide municipal. |
| goioere | SP | 4108601 | Goioerê | 0 | 1 | UF divergente no cadastro Olist. Nome confere com Goioerê/PR, unico municipio com esse nome no pais; prefixo(s) de CEP 87360 a ate 0.0 km do centroide municipal. |
| juiz de fora | SP | 3136702 | Juiz de Fora | 0 | 1 | UF divergente no cadastro Olist. Nome confere com Juiz de Fora/MG, unico municipio com esse nome no pais; prefixo(s) de CEP 36010 a ate 1.1 km do centroide municipal. |
| laguna | SP | 4209409 | Laguna | 0 | 1 | UF divergente no cadastro Olist. Nome confere com Laguna/SC, unico municipio com esse nome no pais; prefixo(s) de CEP 88790 a ate 0.0 km do centroide municipal. |
| laranjeiras do sul | SP | 4113304 | Laranjeiras do Sul | 0 | 1 | UF divergente no cadastro Olist. Nome confere com Laranjeiras do Sul/PR, unico municipio com esse nome no pais; prefixo(s) de CEP 85301 a ate 0.4 km do centroide municipal. |
| londrina | SP | 4113700 | Londrina | 0 | 1 | UF divergente no cadastro Olist. Nome confere com Londrina/PR, unico municipio com esse nome no pais; prefixo(s) de CEP 86076 a ate 2.8 km do centroide municipal. |
| marechal candido rondon | SP | 4114609 | Marechal Cândido Rondon | 0 | 1 | UF divergente no cadastro Olist. Nome confere com Marechal Cândido Rondon/PR, unico municipio com esse nome no pais; prefixo(s) de CEP 85960 a ate 0.0 km do centroide municipal. |
| palhoca | SP | 4211900 | Palhoça | 0 | 1 | UF divergente no cadastro Olist. Nome confere com Palhoça/SC, unico municipio com esse nome no pais; prefixo(s) de CEP 88136 a ate 4.6 km do centroide municipal. |
| pinhais | SP | 4119152 | Pinhais | 0 | 1 | UF divergente no cadastro Olist. Nome confere com Pinhais/PR, unico municipio com esse nome no pais; prefixo(s) de CEP 83321 a ate 1.7 km do centroide municipal. |
| porto alegre | SP | 4314902 | Porto Alegre | 0 | 1 | UF divergente no cadastro Olist. Nome confere com Porto Alegre/RS, unico municipio com esse nome no pais; prefixo(s) de CEP 91520 a ate 3.4 km do centroide municipal. |
| rio bonito | SP | 3304300 | Rio Bonito | 0 | 1 | UF divergente no cadastro Olist. Nome confere com Rio Bonito/RJ, unico municipio com esse nome no pais; prefixo(s) de CEP 28810 a ate 11.3 km do centroide municipal. |
| sao jose dos pinhais | SP | 4125506 | São José dos Pinhais | 0 | 1 | UF divergente no cadastro Olist. Nome confere com São José dos Pinhais/PR, unico municipio com esse nome no pais; prefixo(s) de CEP 83020 a ate 3.1 km do centroide municipal. |
| tocantins | SP | 3169000 | Tocantins | 0 | 1 | UF divergente no cadastro Olist. Nome confere com Tocantins/MG, unico municipio com esse nome no pais; prefixo(s) de CEP 36512 a ate 0.0 km do centroide municipal. |
| vila velha | SP | 3205200 | Vila Velha | 0 | 1 | UF divergente no cadastro Olist. Nome confere com Vila Velha/ES, unico municipio com esse nome no pais; prefixo(s) de CEP 29101 a ate 4.0 km do centroide municipal. |

## Não resolvidos

65 combinação(ões) de cidade e UF sem município. Lista completa:

| Entidade | Cidade no Olist | UF | Registros |
|---|---|---|---:|
| cliente | santo amaro de campos | RJ | 6 |
| cliente | carajas | PA | 4 |
| cliente | extrema | RO | 4 |
| cliente | maioba | MA | 3 |
| cliente | areia branca dos assis | PR | 3 |
| cliente | colonia castrolanda | PR | 3 |
| cliente | domiciano ribeiro | GO | 2 |
| cliente | luizlandia do oeste | MG | 2 |
| cliente | palmeirinha | PR | 2 |
| cliente | monnerat | RJ | 2 |
| cliente | santo eduardo | RJ | 2 |
| cliente | nossa senhora do remedio | SP | 2 |
| cliente | luziapolis | AL | 1 |
| cliente | pau d'arco | AL | 1 |
| cliente | aribice | BA | 1 |
| cliente | humildes | BA | 1 |
| cliente | jacuipe | BA | 1 |
| cliente | jaua | BA | 1 |
| cliente | dourado | CE | 1 |
| cliente | missi | CE | 1 |
| cliente | angelo frechiani | ES | 1 |
| cliente | jardim abc de goias | GO | 1 |
| cliente | brejo bonito | MG | 1 |
| cliente | conceicao do formoso | MG | 1 |
| cliente | cuite velho | MG | 1 |
| cliente | estevao de araujo | MG | 1 |
| cliente | glaura | MG | 1 |
| cliente | guinda | MG | 1 |
| cliente | major porto | MG | 1 |
| cliente | palmital de minas | MG | 1 |
| cliente | pinhotiba | MG | 1 |
| cliente | ponto do marambaia | MG | 1 |
| cliente | sao francisco do humaita | MG | 1 |
| cliente | sao vitor | MG | 1 |
| cliente | serra bonita | MG | 1 |
| cliente | silveira carvalho | MG | 1 |
| cliente | pitanga de estrada | PB | 1 |
| cliente | santo antonio das queimadas | PE | 1 |
| cliente | sao domingos | PE | 1 |
| cliente | siriji | PE | 1 |
| cliente | alto sao joao | PR | 1 |
| cliente | doce grande | PR | 1 |
| cliente | ilha dos valadares | PR | 1 |
| cliente | perola independente | PR | 1 |
| cliente | santa margarida | PR | 1 |
| cliente | santana | PR | 1 |
| cliente | sao clemente | PR | 1 |
| cliente | sao miguel do cambui | PR | 1 |
| cliente | bemposta | RJ | 1 |
| cliente | bom jesus do querendo | RJ | 1 |
| cliente | corrego do ouro | RJ | 1 |
| cliente | ibitioca | RJ | 1 |
| cliente | jaguarembe | RJ | 1 |
| cliente | sao joao do paraiso | RJ | 1 |
| cliente | sao sebastiao de campos | RJ | 1 |
| cliente | sao sebastiao do paraiba | RJ | 1 |
| cliente | poco de pedra | RN | 1 |
| cliente | mutum parana | RO | 1 |
| cliente | ipiranga | RS | 1 |
| cliente | polo petroquimico de triunfo | RS | 1 |
| vendedor | aguas claras df | SP | 1 |
| cliente | cipo-guacu | SP | 1 |
| vendedor | ipira | SP | 1 |
| cliente | pinheiros | SP | 1 |
| cliente | sao sebastiao da serra | SP | 1 |

## Interface Silver → Gold v2

O contrato oficial está em `docs/contrato_entrada_gold.md`.
A Gold usa `clientes_municipios`, `vendedores_municipios`,
`geografia_integrada` e `distancias_itens` como saídas da integração.
Os demais Parquets desta etapa são auxiliares de auditoria.

Os mapeamentos auxiliares usam `de_para`, equivalente a `manual` na interface.
A distância por par usa pontos municipais; a distância por item usa CEPs.
Essas distâncias não são equivalentes. A medida oficial da Gold é a distância por item.

