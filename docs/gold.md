# Gold — implementação e validação

## Execução

```powershell
.venv/Scripts/python.exe -m src.run_pipeline
.venv/Scripts/python.exe -m src.run_pipeline --etapa gold
.venv/Scripts/python.exe -m src.run_pipeline --etapa qualidade
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

O comando completo executa Bronze → Silver → integração → validação → Gold → qualidade; módulos obrigatórios ausentes interrompem o pipeline. Para executar somente a Gold, as onze entradas Silver devem existir e atender ao contrato v2.

## Código

| Arquivo | Responsabilidade |
| --- | --- |
| `src/gold/schema.sql` | DDL das duas fatos e seis dimensões, PKs, unicidade e 12 FKs |
| `src/gold/carga.sql` | Membros SK 0, dimensões ordenadas por chave natural, agregações e joins |
| `src/gold/dimensional.py` | Contrato de entrada, referências, construção transacional e publicação por substituição |
| `src/gold/qualidade.py` | Verificação de integridade, reconciliação por registro e total, cobertura e assinaturas |
| `tests/test_gold.py` | Casos de ausência, vários itens, mesma pessoa com endereços diferentes, repetição e falha sem corromper o DW anterior |

A modelagem física e as classificações estão em [modelo_dimensional.md](modelo_dimensional.md). A interface está em [contrato_entrada_gold.md](contrato_entrada_gold.md).

## Resultado real — 2026-09-15

Contagens incluem um membro desconhecido em cada dimensão:

| Tabela | Linhas |
| --- | ---: |
| `dim_tempo` | 1.097 |
| `dim_produto` | 32.952 |
| `dim_cliente` | 96.097 |
| `dim_vendedor` | 3.096 |
| `dim_geografia` | 5.572 |
| `dim_pagamento` | 29 |
| `fato_pedido` | 99.441 |
| `fato_item_pedido` | 112.650 |

- 59 verificações Gold aprovadas, zero reprovações e zero órfãos nas 12 FKs.
- 775 pedidos sem itens preservados, com contagem e somas de conjunto vazio iguais a zero.
- Somatório técnico de todos os itens, incluindo todos os status: produtos R$ 13591643.70, frete R$ 2251909.54, total R$ 15843553.24. Esses totais reconciliam exatamente com a Silver e não representam o KPI comercial filtrado em entregues.
- Sete testes automatizados passaram (cinco de contrato Silver e dois de integração Gold).
- 16 consultas SELECT/WITH do catálogo de KPIs passaram em EXPLAIN contra o DW real.
- O pipeline completo foi executado sem etapas puladas. A Bronze/Silver manteve seus dez alertas conhecidos; eles não foram convertidos em dados inventados.

## Reprodução da carga

A primeira carga Gold e a carga produzida pela reexecução completa do pipeline geraram os mesmos SHA-256 das oito tabelas. O cálculo inclui todos os registros e tipos, ordenados pela PK, verificando valores e SKs; bytes físicos do DuckDB podem diferir.

| Tabela | SHA-256 das duas cargas |
| --- | --- |
| `dim_tempo` | `e99dbd59d430f939a859db6e7aa5fe2a693cc1ffea27d17fb2928039f98ab9d1` |
| `dim_produto` | `5ed799b22f0b494f448b8c589b935f363b94bde9246f5714faef6bcbdaa56ec8` |
| `dim_cliente` | `58a6c9e49a508a8eda51fdaadc53f83819b9ace2a95987818391da53ac9ad6de` |
| `dim_vendedor` | `af1760493e17d8488c99f6973d8656b9cb52f880eae6053bf261ce6fc284d90b` |
| `dim_geografia` | `da62ee66f751f1aa09cb857da22190c59c38d6183095cdc6d1d411039348ef90` |
| `dim_pagamento` | `5a744ee8faafc162e1757837ac27ca7919fd73291d4a225b28645c7cb4d515cd` |
| `fato_pedido` | `7e01416c373520147a206485bc5cfd0ef45de1b3901dace61205940d1f5b7e7f` |
| `fato_item_pedido` | `51e2737ba4a8832614a6bdc5495af8dad85e85f6e13dcf1ee331af2ece4c4509` |

As evidências locais estão em `data/gold/reprodutibilidade.json`, `data/gold/qualidade.json`, `data/gold/qualidade.md` e `data/gold/pipeline_completo.log`. Saídas geradas não são versionadas; este documento registra o resultado conferido nesta revisão.

## Uso e limites

O dashboard deve consultar apenas `data/gold/dw.duckdb`. As oito tabelas são persistidas; nenhuma leitura de Parquet ou tabela de estágio é necessária ao consumidor.

A carga é completa, SCD Tipo 1. Uma mudança nas chaves naturais pode renumerar SKs; todas as tabelas são reconstruídas e publicadas juntas. Não há manutenção incremental nem histórico de versões.

Nulos legítimos continuam nulos. Se algum item tem componente monetário desconhecido, o total correspondente do pedido também fica nulo. Somente pedidos sem qualquer item recebem somas zero. `valor_total_pago` é auditável por pedido e nunca é repetido na fato de itens.

A geografia da pessoa é resolvida por cadastro do pedido. As coordenadas municipais continuam aproximadas e os indicadores socioeconômicos representam 2017. O membro técnico preserva relações não resolvidas sem inventar município ou data.
