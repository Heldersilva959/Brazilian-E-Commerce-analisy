# Regras de Tratamento de Geolocalização e Matching (Olist + IBGE)

Este documento estabelece os critérios e regras de negócio para a preparação da camada Silver de geolocalização, que integra a base de clientes/vendedores do Olist com a base oficial de municípios do IBGE.

## 1. Validade das Coordenadas (Bounding Box do Brasil)
Para limpar dados de GPS corrompidos (como coordenadas no meio do oceano ou em outros continentes, um problema comum no dataset do Olist), aplicamos a seguinte trava geográfica que abrange o território brasileiro:
*   **Latitude**: deve estar contida entre **5.5°** e **-34.0°**.
*   **Longitude**: deve estar contida entre **-74.0°** e **-34.0°**.
*   **Ação**: Qualquer coordenada fora desse quadrante é sumariamente descartada antes de qualquer cálculo.

## 2. Normalização de Texto
Como os dados do Olist (input manual de usuários) e do IBGE (base oficial) possuem padrões diferentes, todas as strings de "nome de cidade" passam obrigatoriamente por este fluxo:
*   Remoção de acentos (ex: "São Paulo" -> "sao paulo").
*   Conversão integral para letras minúsculas.
*   Remoção de aspas (simples e duplas) e apóstrofos.
*   Substituição de hifens por espaços em branco.
*   Remoção de espaços extras nas extremidades (strip) e compactação de múltiplos espaços sequenciais.

## 3. Formação de Pontos Representativos Municipais (Centroides)
O dataset do Olist possui múltiplos registros de latitude/longitude para o mesmo prefixo de CEP e mesma cidade. Em vez de escolhermos uma coordenada aleatória, calculamos um centroide por cidade.
*   **Métrica Utilizada**: Mediana Espacial (mediana da latitude e mediana da longitude).
*   **Motivo da Escolha**: A média simples é altamente suscetível a *outliers* (erros de GPS que caíram dentro da bounding box mas fora da cidade real). A mediana garante que o ponto representativo ficará na região com maior densidade (o "centro de massa" onde a maioria dos clientes daquela cidade de fato reside).
*   **Agrupamento**: A agregação é feita pela chave composta `[estado, cidade_norm]`.

## 4. Ambiguidade e Critério de Match Exato
*   **Match Exato**: A chave estrangeira (`ibge_id`) só é associada ao Olist se a combinação `(estado, cidade_norm)` for 100% idêntica em ambas as bases pós-processamento.
*   **Resolução de Nomes Ambíguos**: Existem diversas cidades com o mesmo nome em estados diferentes do Brasil (ex: "Bom Jesus" ou "Aparecida"). O agrupamento estrito incluindo a UF (`estado`) resolve naturalmente essa ambiguidade.
*   **Tratamento de Exceções**: Cidades presentes no Olist que não encontram match perfeito com o IBGE (erros grosseiros de digitação ou nomes não-oficiais de distritos) são separadas no artefato `report_unmatched_cities.csv`. Elas não sobem para a camada Gold automaticamente, ficando aguardando a criação de um dicionário manual (`de_para_municipios.csv`) ou aplicação futura de algoritmo *Fuzzy Matching*.