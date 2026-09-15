import pandas as pd
import json
import os
import sys

# Adiciona o diretório src ao path para importar o utilitário
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.normalizer import normalize_city_name

# Caminhos dos arquivos (ajuste conforme a raiz da execução)
RAW_OLIST_GEO = 'data/raw/olist/olist_geolocation_dataset.csv'
RAW_IBGE = 'data/raw/ibge/municipios.json'
SILVER_OUT = 'data/silver/olist_ibge_matched.csv'
REPORT_MATCHED = 'data/silver/report_matched_cities.csv'
REPORT_UNMATCHED = 'data/silver/report_unmatched_cities.csv'

def load_and_prep_ibge(filepath):
    print("Processando JSON do IBGE...")
    with open(filepath, 'r', encoding='utf-8') as f:
        ibge_data = json.load(f)
        
    ibge_list = []
    for mun in ibge_data:
        uf = mun['microrregiao']['mesorregiao']['UF']['sigla']
        nome = mun['nome']
        ibge_list.append({
            'ibge_id': mun['id'],
            'estado': uf,
            'cidade_ibge_original': nome,
            'cidade_norm': normalize_city_name(nome)
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
    
    return centroids

def execute_matching():
    df_ibge = load_and_prep_ibge(RAW_IBGE)
    df_olist = load_and_prep_olist_geo(RAW_OLIST_GEO)
    
    print("Realizando match exato...")
    # Left join partindo do Olist para ver o que achou ou não no IBGE
    df_merged = pd.merge(
        df_olist, 
        df_ibge, 
        on=['estado', 'cidade_norm'], 
        how='left'
    )
    
    # Separando os resultados para os relatórios
    matched = df_merged[df_merged['ibge_id'].notnull()].copy()
    unmatched = df_merged[df_merged['ibge_id'].isnull()].copy()
    
    # Garantindo diretórios
    os.makedirs('data/silver', exist_ok=True)
    
    # Exportando tabela final consolidada
    matched.to_csv(SILVER_OUT, index=False)
    
    # Exportando Relatórios
    matched[['estado', 'cidade_norm', 'cidade_ibge_original', 'ibge_id', 'qte_pontos']].to_csv(REPORT_MATCHED, index=False)
    unmatched[['estado', 'cidade_norm', 'qte_pontos']].sort_values(by='qte_pontos', ascending=False).to_csv(REPORT_UNMATCHED, index=False)
    
    print("-" * 30)
    print("RESUMO DO MATCHING:")
    print(f"Cidades únicas no Olist (pós-filtro de coord): {len(df_olist)}")
    print(f"Match Exato com IBGE: {len(matched)} ({len(matched)/len(df_olist):.1%})")
    print(f"Não encontradas no IBGE: {len(unmatched)}")
    print(f"Dados salvos em data/silver/")
    print("-" * 30)

if __name__ == '__main__':
    execute_matching()