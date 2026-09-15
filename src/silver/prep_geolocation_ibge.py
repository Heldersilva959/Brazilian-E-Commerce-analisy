import pandas as pd
import json
import os
import sys

# Adiciona o diretório src ao path para importar o utilitário
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.normalizacao import chave_sem_espacos, normalizar_texto as normalize_city_name

# Caminhos dos arquivos (ajuste conforme a raiz da execução)
RAW_OLIST_GEO = 'data/raw/olist/olist_geolocation_dataset.csv'
RAW_IBGE = 'data/raw/ibge/municipios.json'
SILVER_OUT = 'data/silver/olist_ibge_matched.csv'
REPORT_MATCHED = 'data/silver/report_matched_cities.csv'
REPORT_UNMATCHED = 'data/silver/report_unmatched_cities.csv'

def extrair_uf(mun):
    """
    Devolve a sigla da UF de um municipio do JSON de localidades do IBGE.

    A hierarquia usual e microrregiao > mesorregiao > UF, mas ha municipio
    recente sem microrregiao (`microrregiao: null`). Nesse caso a UF so
    aparece em regiao-imediata > regiao-intermediaria > UF.
    """
    microrregiao = mun.get('microrregiao')
    if microrregiao:
        return microrregiao['mesorregiao']['UF']['sigla']

    regiao_imediata = mun.get('regiao-imediata')
    if regiao_imediata:
        return regiao_imediata['regiao-intermediaria']['UF']['sigla']

    raise ValueError(f"Municipio {mun['id']} ({mun['nome']}) sem UF identificavel no JSON do IBGE")

def load_and_prep_ibge(filepath):
    print("Processando JSON do IBGE...")
    with open(filepath, 'r', encoding='utf-8') as f:
        ibge_data = json.load(f)
        
    ibge_list = []
    for mun in ibge_data:
        uf = extrair_uf(mun)
        nome = mun['nome']
        cidade_norm = normalize_city_name(nome)
        ibge_list.append({
            # Codigo como texto de 7 posicoes: o contrato pede VARCHAR(7). Se
            # ficar numerico, o merge com ausentes promove a coluna para float
            # e o codigo sai gravado como "1200013.0".
            'ibge_id': f"{mun['id']:07d}",
            'estado': uf,
            'cidade_ibge_original': nome,
            'cidade_norm': cidade_norm,
            'chave_sem_espaco': chave_sem_espacos(cidade_norm)
        })

    return pd.DataFrame(ibge_list)

def load_and_prep_olist_geo(filepath):
    print("Processando coordenadas do Olist...")
    df_geo = pd.read_csv(filepath)
    
    # 1. Filtro de Bounding Box do Brasil para remover lixo geográfico
    df_geo = df_geo[
        (df_geo['geolocation_lat'] >= -34.0) & (df_geo['geolocation_lat'] <= 5.5) &
        (df_geo['geolocation_lng'] >= -74.0) & (df_geo['geolocation_lng'] <= -34.0)
    ]
    
    # 2. Normalização
    df_geo['cidade_norm'] = df_geo['geolocation_city'].apply(normalize_city_name)
    df_geo['estado'] = df_geo['geolocation_state']
    
    # 3. Calcular ponto representativo (mediana) por cidade/estado
    print("Calculando centroides (mediana) por município...")
    centroids = df_geo.groupby(['estado', 'cidade_norm']).agg(
        lat_representativa=('geolocation_lat', 'median'),
        lng_representativa=('geolocation_lng', 'median'),
        qte_pontos=('geolocation_zip_code_prefix', 'count')
    ).reset_index()

    centroids['chave_sem_espaco'] = centroids['cidade_norm'].apply(chave_sem_espacos)

    return centroids

def execute_matching():
    df_ibge = load_and_prep_ibge(RAW_IBGE)
    df_olist = load_and_prep_olist_geo(RAW_OLIST_GEO)

    df_ibge = df_ibge[['estado', 'cidade_norm', 'chave_sem_espaco', 'ibge_id', 'cidade_ibge_original']]

    # --- 1a passada: nome normalizado identico ---
    print("Realizando match exato (nome identico)...")
    # Left join partindo do Olist para ver o que achou ou não no IBGE
    passo1 = pd.merge(
        df_olist,
        df_ibge.drop(columns=['chave_sem_espaco']),
        on=['estado', 'cidade_norm'],
        how='left'
    )

    matched_1 = passo1[passo1['ibge_id'].notnull()].copy()
    matched_1['variante_match'] = 'nome_identico'

    residuo = passo1[passo1['ibge_id'].isnull()].drop(columns=['ibge_id', 'cidade_ibge_original'])

    # --- 2a passada: mesmo nome ignorando os espacos ---
    # So entra aqui o que a 1a passada nao resolveu, entao a 2a nunca sobrepoe
    # um match de nome identico. A chave precisa ser unica dentro da UF: se
    # houver colisao, o municipio fica de fora em vez de ser escolhido no acaso.
    print("Realizando match exato (ignorando espacos)...")
    ibge_sem_espaco = df_ibge.drop(columns=['cidade_norm'])
    colisoes = ibge_sem_espaco.duplicated(['estado', 'chave_sem_espaco'], keep=False)
    if colisoes.any():
        print(f"  AVISO: {colisoes.sum()} municipios do IBGE com chave ambigua; ficam fora desta passada.")
        ibge_sem_espaco = ibge_sem_espaco[~colisoes]

    passo2 = pd.merge(
        residuo,
        ibge_sem_espaco,
        on=['estado', 'chave_sem_espaco'],
        how='left'
    )

    matched_2 = passo2[passo2['ibge_id'].notnull()].copy()
    matched_2['variante_match'] = 'sem_espacos'
    unmatched = passo2[passo2['ibge_id'].isnull()].copy()

    # As duas passadas sao o metodo "exato" do contrato; a variante fica
    # registrada a parte para o relatorio de match ser auditavel.
    matched = pd.concat([matched_1, matched_2], ignore_index=True)
    matched['metodo_match'] = 'exato'

    # Condicao de aceite: uma cidade do Olist nao pode sair com dois codigos.
    duplicadas = matched.duplicated(['estado', 'cidade_norm']).sum()
    if duplicadas:
        raise ValueError(f"{duplicadas} cidades com mais de um cod_ibge apos o match")

    # Garantindo diretórios
    os.makedirs('data/silver', exist_ok=True)

    # Exportando tabela final consolidada
    matched.to_csv(SILVER_OUT, index=False)

    # Exportando Relatórios
    matched[['estado', 'cidade_norm', 'cidade_ibge_original', 'ibge_id', 'metodo_match', 'variante_match', 'qte_pontos']].to_csv(REPORT_MATCHED, index=False)
    unmatched[['estado', 'cidade_norm', 'qte_pontos']].sort_values(by='qte_pontos', ascending=False).to_csv(REPORT_UNMATCHED, index=False)

    total = len(df_olist)
    print("-" * 30)
    print("RESUMO DO MATCHING:")
    print(f"Cidades únicas no Olist (pós-filtro de coord): {total}")
    print(f"  match por nome idêntico:   {len(matched_1)} ({len(matched_1)/total:.1%})")
    print(f"  match ignorando espaços:   {len(matched_2)} ({len(matched_2)/total:.1%})")
    print(f"Match Exato com IBGE: {len(matched)} ({len(matched)/total:.1%})")
    print(f"Não encontradas no IBGE: {len(unmatched)}")
    print(f"Cobertura por volume de pontos: {matched['qte_pontos'].sum()/df_olist['qte_pontos'].sum():.2%}")
    print(f"Dados salvos em data/silver/")
    print("-" * 30)

if __name__ == '__main__':
    execute_matching()