# Regras da integração geográfica (Olist + IBGE)

Critérios de negócio da etapa do membro 3, implementada em
`src/silver/integracao_municipios.py`. Os números de cada execução ficam em
`docs/relatorio_match.md`, que é gerado pelo código — este documento explica
**por que** cada regra é assim.

## 1. De onde vêm os dados

A integração lê só a camada silver, nunca os CSV originais nem a bronze
(contrato de dados §5.2):

| Entrada | Para quê |
| --- | --- |
| `silver/municipios.parquet` | cadastro canônico do IBGE + indicadores do SIDRA |
| `silver/geolocalizacao_cep.parquet` | mediana de lat/lng por prefixo de CEP |
| `silver/clientes.parquet`, `silver/vendedores.parquet` | as entidades a resolver |
| `silver/pedidos.parquet`, `silver/itens_pedido.parquet` | grão das distâncias |
| `de_para_municipios.csv` | correções manuais, versionadas com evidência |

A limpeza das coordenadas não está mais aqui: a caixa delimitadora do Brasil é
aplicada pela silver, que marca `flag_coordenada_invalida` e exclui esses
pontos do cálculo da mediana por CEP. Nos dados reais isso descarta 42 dos
1.000.163 pontos. Manter o filtro em dois lugares seria duplicar regra.

## 2. Normalização de texto

Uma implementação só no repositório, `normalizar_texto()` em
`src/utils/normalizacao.py` (contrato §5.1): minúsculas → NFKD sem
combinantes → tudo que não é letra, número ou espaço vira espaço → colapso de
espaços → strip.

O separador vira **espaço** em vez de sumir. Isso é deliberado: `Embu-Guaçu`
resulta em `embu guacu` e `Santa Bárbara d'Oeste` em `santa barbara d oeste`,
que são as formas mais frequentes no Olist.

## 3. Ordem dos métodos

| # | Método | Regra |
| --- | --- | --- |
| 1 | `exato` | `(municipio_normalizado, uf)` idênticos |
| 1b | `exato` | mesma chave **ignorando espaços**, só quando única na UF |
| 2 | `de_para` | correção manual versionada, com justificativa |
| 3 | `geografico` | centroide municipal mais próximo na mesma UF, até 50 km |
| 4 | `nao_resolvido` | `cod_ibge` nulo e motivo registrado |

**Nunca casar só por nome.** "Bom Jesus" existe em vários estados; a UF entra
em toda comparação de nome.

**Por que a passada 1b existe.** O Olist escreve o mesmo município de duas
formas, e as duas aparecem na base: `mirassol doeste` (101 pontos) e
`mirassol d oeste` (5 pontos). No sentido inverso, o IBGE traz `Embu-Guaçu`
(que normaliza para `embu guacu`) enquanto o Olist escreve `embuguacu`.
Nenhuma regra única de normalização casa as duas grafias. Comparar o nome sem
nenhum espaço resolve as duas de uma vez, e só é aplicada quando a chave é
única dentro da UF — se duas cidades da mesma UF colapsarem na mesma chave,
nenhuma das duas pode ser casada por ela.

**Por que o de-para vem antes do geográfico.** O de-para é evidência
conferida; o geográfico é inferência por proximidade. Deixar o geográfico na
frente faria uma estimativa sobrepor um fato verificado.

## 4. Formação do ponto representativo municipal

O centroide de um município é a **mediana** das coordenadas dos prefixos de
CEP associados a ele — e só dos prefixos resolvidos pelo **método exato**.

- Mediana e não média: mesmo depois do filtro da caixa do Brasil sobram erros
  de GPS dentro do território. A média é arrastada por eles; a mediana fica na
  região de maior densidade.
- Só matches exatos: se um prefixo resolvido por aproximação entrasse na
  formação do centroide, o fallback passaria a aproximar os próximos casos a
  partir do próprio erro.

Resultado real: 18.325 dos 19.010 prefixos de CEP resolvidos por nome, que
formam centroide para 5.450 dos 5.571 municípios.

## 5. Fallback geográfico

Para a entidade que sobrou, a mediana do seu prefixo de CEP é comparada com os
centroides dos municípios **da mesma UF**, e vence o mais próximo, desde que
esteja a **até 50 km**. Acima disso o caso fica como não resolvido: um
município nulo é melhor que um município errado, porque a gold mapeia nulo
para o membro técnico e o erro não se propaga em silêncio.

Empate de distância é desempatado por `cod_ibge`, para a segunda execução
produzir exatamente o mesmo resultado.

## 6. De-para manual — o que conta como evidência

O arquivo `de_para_municipios.csv` é versionado e tem as colunas do contrato:
`cidade_origem`, `uf_origem`, `cod_ibge`, `justificativa`. Uma linha só entra
com evidência registrada na própria justificativa. Nunca por palpite.

As 23 entradas atuais são todas do mesmo tipo: **vendedor com a UF digitada
errada no cadastro**. Cada uma exigiu duas evidências independentes que
concordam:

1. O nome normalizado corresponde a **exatamente um** município no país
   inteiro — se houvesse dois homônimos, a entrada não entraria.
2. O prefixo de CEP do vendedor cai a menos de 50 km do centroide **desse**
   município.

Exemplo: `curitiba/SP` → `4106902` (Curitiba/PR), com os prefixos 80240, 81020
e 81560 a até 7,3 km do centroide de Curitiba.

**O que deliberadamente ficou de fora.** Buscar o município mais próximo
ignorando a UF declarada, sem a confirmação do nome, produz absurdos: o CEP
28140 (`santo amaro de campos/RJ`) cai a 8,6 km do centroide de Taboão da
Serra/SP, porque a coordenada daquele prefixo está corrompida na base do
Olist. Só a distância não é evidência — é preciso o nome concordar.

## 7. Distâncias

Duas tabelas, porque os dois contratos pedem grãos diferentes:

| Arquivo | Grão | Coordenadas usadas |
| --- | --- | --- |
| `distancias_vendedor_cliente.parquet` | par `(seller_id, customer_id)` | centroides municipais (contrato §5.3) |
| `distancias_itens.parquet` | `(order_id, order_item_id)` | medianas dos prefixos de CEP (contrato da gold §14.4) |

Haversine com raio médio de 6.371,0088 km. **Não é distância rodoviária** — é
a geodésica entre pontos aproximados. Se qualquer um dos lados não tiver
coordenada, a distância fica nula e o motivo é registrado; nada é preenchido
com zero.

Sanidade dos números reais: SP→SP 151 km em média, SP→RJ 442 km, SP→RS 907 km,
SP→AM 2.637 km.

## 8. Condições de aceite

A etapa falha em vez de gravar um arquivo que quebraria a gold:

- uma linha por `customer_id` e uma por `seller_id`;
- uma linha por `(order_id, order_item_id)`;
- todo `cod_ibge` preenchido existe no cadastro do IBGE;
- `distancia_match_km` só aparece no método `geografico`;
- nenhum fallback geográfico acima de 50 km;
- `de_para_municipios.csv` sem código inexistente e sem `(cidade, uf)` repetido.

Uma linha duplicada nos mapeamentos multiplicaria itens na fato e quebraria o
faturamento sem aviso — por isso a checagem é bloqueante.

## 9. Limitações conhecidas

- As coordenadas são derivadas do Olist, não são centroides oficiais do IBGE.
- Distrito não é município: `santo amaro de campos/RJ` e outros distritos só
  seriam resolvidos com uma fonte externa de distritos, que o grupo não usa.
- Prefixos de CEP sem nenhuma coordenada válida na base não têm como ser
  resolvidos pelo fallback — é a causa da maior parte do resíduo de clientes.
- O resíduo atual é 86 clientes (0,09%) e 2 vendedores (0,06%). A lista
  completa e auditável fica em `data/silver/municipios_nao_resolvidos.csv`.
