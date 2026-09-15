# Revisão da integração geográfica — membro 3

**Data:** 15/09/2026
**Objeto inicial:** commit `9e14f29` ("feat(silver): implementa normalização e match exato de geolocalização Olist/IBGE"), integrado ao `main` pelo merge `3d26ed1` (PR #4).
**Branch desta rodada:** `codex/integracao-municipios`
**Situação:** etapa concluída. O pipeline executa bronze → silver → integração de ponta a ponta, com as condições de aceite verificadas e resultado idêntico entre execuções.

As regras de negócio da etapa estão em `docs/regras_geolocalizacao.md`; os
números de cada execução, em `docs/relatorio_match.md` (gerado pelo código).
Este documento registra o que a revisão encontrou e o que foi feito.

---

## 1. O que a revisão encontrou

O merge do PR #4 entrou limpo e puramente aditivo — sem conflito nem regressão
sobre bronze e silver. Mas a etapa não rodava e não produzia nenhum dos
entregáveis do contrato:

| Achado | Situação |
| --- | --- |
| Script abortava no JSON real do IBGE | corrigido (§3.1) |
| `run_pipeline` pulava a etapa inteira | corrigido (§4) |
| Silver não entregava `municipios.parquet` | corrigido (§5) |
| Nenhum mapeamento, distância ou relatório existia | corrigido (§4) |
| `de_para_municipios.csv` vazio e com colunas fora do contrato | corrigido (§6) |
| Duas implementações de normalização no repositório | corrigido (§3.2) |

---

## 2. Ambiente de execução

O `requirements.txt` fixa `pandas==2.2.3`, e **esse pin não tem wheel publicado
para o Python 3.14**: o `pip` cai para compilação do fonte e falha por ausência
de MSVC. O mesmo vale para `pyarrow==18.0.0`. Para cp314 o pandas mais antigo
disponível é o 2.3.3.

Solução adotada, preservando os pins do contrato:

1. Python **3.12.10** instalado via `winget install Python.Python.3.12`.
2. `py -3.12 -m venv .venv` na raiz do repositório (já coberto pelo `.gitignore`).
3. `pip install --only-binary=:all: -r requirements.txt` — sem compilação de fonte.

```
pandas 2.2.3 | pyarrow 18.0.0 | duckdb 1.5.5 | requests 2.32.3 | numpy 2.5.3
```

> **Para o membro 1 (dono do `requirements.txt`):** quem estiver no Python 3.14
> não consegue montar este ambiente. Vale registrar o Python 3.12 como versão
> oficial do grupo no README, ou afrouxar os pins. Não mexi no arquivo por ser
> de outro responsável.

---

## 3. Correções no código existente

### 3.1 Município sem microrregião derrubava o script

`prep_geolocation_ibge.py` abortava na primeira função, antes de gravar
qualquer arquivo:

```
uf = mun['microrregiao']['mesorregiao']['UF']['sigla']
TypeError: 'NoneType' object is not subscriptable
```

Dos 5.571 municípios, **um** tem `microrregiao: null` — `5101837`, Boa
Esperança do Norte/MT, criado depois da última revisão da malha. A UF dele só
existe em `regiao-imediata > regiao-intermediaria > UF`. Não era problema de
versão de biblioteca: o erro é idêntico no pandas 2.2.3 e no 3.0.5. O membro 1
encontrou o mesmo município na bronze e já o tratava.

A leitura da UF saiu para `extrair_uf(mun)`, com fallback para a região
imediata e `ValueError` identificando o município se nenhum ramo existir. A
mesma regra foi aplicada em `municipios.parquet` (§5).

### 3.2 Uma normalização só, como manda o contrato

Havia `normalizer.py` / `normalize_city_name()` com passos diferentes dos do
contrato §5.1. Agora:

- `src/utils/normalizacao.py` é a implementação canônica, com
  `normalizar_texto()` e `chave_sem_espacos()`;
- `src/utils/normalizer.py` virou um apelido fino que delega para ela — zero
  lógica própria, e o protótipo continua rodando;
- `registrar_no_duckdb()` expõe as duas ao SQL, então a silver e a integração
  normalizam pelo mesmo código Python, sem uma segunda versão escrita em SQL
  que pudesse divergir em silêncio.

### 3.3 Segunda passada do match exato, e `cod_ibge` como texto

O Olist grafa o mesmo município de duas formas: `mirassol doeste` (101 pontos)
e `mirassol d oeste` (5 pontos); e no sentido inverso, `embuguacu` contra o
`Embu-Guaçu` do IBGE. Comparar o nome sem nenhum espaço resolve as duas de uma
vez — aplicado só sobre o resíduo da primeira passada e só quando a chave é
única na UF. O `cod_ibge` passou a ser texto de 7 posições na origem, em vez de
sair como `1200013.0` depois de um merge com ausentes.

---

## 4. Etapa da integração implementada

`src/silver/integracao_municipios.py` — o nome que o `run_pipeline` procura,
com `executar()`. Lê só a silver, como manda o contrato §5.2.

Ordem dos métodos: `exato` → `exato` sem espaços → `de_para` → `geografico`
(≤ 50 km, mesma UF) → `nao_resolvido`. O de-para vem antes do geográfico porque
é evidência conferida, e o geográfico é inferência por proximidade.

Os centroides municipais saem da mediana dos prefixos de CEP resolvidos
**apenas** pelo método exato, para o fallback não realimentar o próprio erro:
18.325 dos 19.010 prefixos resolvidos por nome, formando centroide para 5.450
dos 5.571 municípios.

### Resultado real

| | Clientes | Vendedores |
| --- | ---: | ---: |
| exato | 98.853 (99,41%) | 2.994 (96,74%) |
| de_para | 0 | 29 (0,94%) |
| geografico | 502 (0,50%) | 70 (2,26%) |
| não resolvido | 86 (0,09%) | 2 (0,06%) |
| **taxa de resolução** | **99,91%** | **99,94%** |

Distâncias: 112.095 dos 112.650 itens com distância calculada. Os 555 restantes
têm o motivo registrado — prefixo de CEP sem coordenada válida de um dos lados.
Sanidade: SP→SP 151 km em média, SP→RJ 442 km, SP→RS 907 km, SP→AM 2.637 km.

### Os dois contratos divergem

`docs/contratos_dados.md` (§5.3) e `docs/contrato_entrada_gold.md` (§11–15)
pedem as mesmas informações com nomes de arquivo, de coluna e vocabulário
diferentes:

| §5.3 (contrato de dados) | §11–15 (entrada da gold) |
| --- | --- |
| `municipios_cliente.parquet` | `clientes_municipios.parquet` |
| `municipios_vendedor.parquet` | `vendedores_municipios.parquet` |
| `distancias_vendedor_cliente.parquet` (par, centroides) | `distancias_itens.parquet` (item, medianas de CEP) |
| método `de_para` | método `manual` |
| — | `geografia_integrada.parquet` |

Não dava para escolher um e ignorar o outro sem quebrar um dos dois membros.
A etapa grava as duas famílias a partir do mesmo cálculo, cada uma no formato
do seu contrato — os números são idênticos, muda a embalagem. **Isto é uma
solução provisória:** o grupo precisa unificar os dois textos antes da entrega
final, e aí uma das famílias sai.

---

## 5. Pendência do membro 2 resolvida

`silver/municipios.parquet` (contrato §4.9) não existia, e sem ele a
integração não tinha cadastro municipal nem indicadores para a gold.

Implementado como `transformar_municipios()` em `src/silver/transform.py`,
no estilo das outras transformações da camada: junção IBGE + SIDRA **pelo
código**, nunca por nome. 5.571 linhas, `cod_ibge` único, nenhuma UF nula. Um
único município sem indicadores do SIDRA — o mesmo 5101837, que não existia em
2017 — e por isso com `porte_municipio = 'Não informado'`. Documentado na seção
12 de `docs/silver_contrato.md`.

---

## 6. De-para preenchido — só com evidência

23 entradas, todas do mesmo tipo: **vendedor com a UF digitada errada**. Cada
uma exigiu duas evidências independentes que concordam:

1. o nome normalizado corresponde a **exatamente um** município no país;
2. o prefixo de CEP cai a menos de 50 km do centroide **desse** município.

Exemplo: `curitiba/SP` → `4106902` (Curitiba/PR), prefixos 80240, 81020 e 81560
a até 7,3 km do centroide. As 23 justificativas estão no próprio CSV e são
reproduzidas em `docs/relatorio_match.md`.

**O que ficou de fora de propósito.** Buscar o município mais próximo ignorando
a UF, sem a confirmação do nome, produz absurdos: o CEP 28140
(`santo amaro de campos/RJ`) cai a 8,6 km do centroide de Taboão da Serra/SP,
porque a coordenada daquele prefixo está corrompida no Olist. Distância
sozinha não é evidência.

O resíduo restante — 86 clientes e 2 vendedores — é sobretudo distrito que não
é município, e prefixo de CEP sem nenhuma coordenada válida na base. Resolver
exigiria uma fonte externa de distritos, que o grupo não usa. Lista completa e
auditável em `data/silver/municipios_nao_resolvidos.csv`.

---

## 7. Testes

Não existe suíte automatizada no repositório — nenhum `tests/`, `test_*.py`,
`pytest.ini` ou `pyproject.toml`. A verificação é o pipeline de ponta a ponta
mais as condições de aceite do contrato conferidas contra as saídas reais.

### 7.1 Membro 1 — bronze: concluído

11 tabelas, contagens preservadas na íntegra, as 4 colunas de linhagem, os
1.027 CEPs com zero à esquerda intactos, cache do IBGE sem acesso à rede, e
`_data_ingestao` marcada `(preservada)` nas 11 tabelas na segunda execução.

### 7.2 Membro 2 — silver: concluído

10 tabelas. Zero duplicatas nas 8 PKs; pagamentos e avaliações com uma linha
por pedido; 112.650 itens preservados sem multiplicação; **zero órfãos** em
`itens → pedidos`, `pedidos → clientes`, `itens → vendedores` e
`itens → produtos`. `municipios.parquet` agora existe (§5).

Fica uma divergência de nome, não de conteúdo: o contrato §4.8 chama de
`geolocalizacao_agregada.parquet` o que a silver grava como
`geolocalizacao_cep.parquet` — mesmo grão, mesmo conteúdo. Vale alinhar o
texto numa revisão de contrato.

### 7.3 Membro 3 — integração: concluído

Etapa executada pelo `run_pipeline` (7 tabelas, 423.303 linhas). Entregáveis
presentes: os dois mapeamentos nas duas famílias de nome, as duas tabelas de
distância, `geografia_integrada.parquet`,
`qualidade_integracao_municipios.json`, `municipios_nao_resolvidos.csv` e
`docs/relatorio_match.md`.

Seis condições de aceite conferidas dentro da própria etapa, que falha em vez
de gravar arquivo inválido: unicidade por `customer_id`, por `seller_id` e por
`(order_id, order_item_id)`; todo `cod_ibge` existente no cadastro do IBGE;
`distancia_match_km` só no método geográfico; nenhum fallback acima de 50 km.
Mais as validações do de-para: nenhum código inexistente, nenhum
`(cidade, uf)` repetido.

### 7.4 Determinismo — critério de conclusão do grupo

Pipeline executado duas vezes; 32 artefatos comparados por contagem de linhas
e hash de conteúdo independente de ordem (sha256 nos CSV), ignorando só a
`_data_ingestao`, que é conferida à parte:

```
DETERMINISMO: 32 artefatos comparados, 0 divergencias
```

Vale para as camadas que existem. Gold e qualidade ainda não foram escritas.

---

## 8. O que continua em aberto

- **Gold e qualidade (membro 4)** — únicas etapas que o pipeline ainda pula.
- **Unificar os dois contratos** (§4). Enquanto não for feito, a integração
  grava arquivo duplicado sob dois nomes.
- **Alinhar `geolocalizacao_agregada` x `geolocalizacao_cep`** (§7.2).
- **Python oficial do grupo** no README (§2).
- **`src/silver/prep_geolocation_ibge.py`** é o protótipo que originou a etapa
  e hoje está coberto por `integracao_municipios.py`. Continua funcionando e
  grava três CSV fora do contrato em `data/silver/`. Removê-lo é decisão da
  dona do arquivo — não mexi.

---

## 9. Como reproduzir

```powershell
.venv\Scripts\python.exe -m src.run_pipeline
```

Ou só a integração, com a silver já materializada:

```powershell
.venv\Scripts\python.exe -m src.silver.integracao_municipios
```

---

## Alterações desta rodada

| Alteração | Arquivo |
| --- | --- |
| `extrair_uf()`, 2ª passada do match, `cod_ibge` como texto, checagem de unicidade | `src/silver/prep_geolocation_ibge.py` |
| Normalização canônica do grupo (`normalizar_texto`, `chave_sem_espacos`, UDF do DuckDB) | `src/utils/normalizacao.py` (novo) |
| Apelido fino para o nome antigo, sem lógica própria | `src/utils/normalizer.py` |
| `transformar_municipios()` — pendência do membro 2 | `src/silver/transform.py` |
| Etapa completa da integração | `src/silver/integracao_municipios.py` (novo) |
| 23 entradas com evidência, colunas do contrato | `de_para_municipios.csv` |
| Regras da etapa, reescritas para o que foi implementado | `docs/regras_geolocalizacao.md` |
| Seção 12 (`municipios`) e pendência de porte resolvida | `docs/silver_contrato.md` |
| Relatório de match — gerado pelo código, não editar à mão | `docs/relatorio_match.md` (novo) |
| Este documento | `docs/revisao_integracao_geografica.md` (novo) |

Fora do Git: `.venv/`, as saídas em `data/bronze/` e `data/silver/`, e o
Python 3.12.10 instalado na máquina. Não foram alterados `requirements.txt`,
`src/bronze/ingest.py`, `src/run_pipeline.py` nem os documentos dos membros 1 e 4.
