import unicodedata
import re

def normalize_city_name(city_name: str) -> str:
    """
    Remove acentos, converte para minúsculas e remove espaços extras/caracteres especiais.
    """
    if not isinstance(city_name, str):
        return ""
    
    # Remove acentos
    normalized = unicodedata.normalize('NFKD', city_name).encode('ASCII', 'ignore').decode('utf-8')
    
    # Converte para minúsculas
    normalized = normalized.lower()
    
    # Remove aspas, apóstrofos e hifens (substitui hifen por espaço para manter padrão)
    normalized = re.sub(r"['\"]", "", normalized)
    normalized = normalized.replace('-', ' ')
    
    # Remove múltiplos espaços
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized