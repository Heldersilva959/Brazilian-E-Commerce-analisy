"""Compatibilidade: o nome antigo da normalizacao.

A implementacao canonica passou para `src/utils/normalizacao.py`, com o nome
de funcao que o contrato de dados fixa (secao 5.1). Este modulo continua aqui
so para nao quebrar `src/silver/prep_geolocation_ibge.py`, que foi o
prototipo do match exato.

Codigo novo importa de `src.utils.normalizacao`.
"""

from __future__ import annotations

from .normalizacao import chave_sem_espacos, normalizar_texto

__all__ = ["normalize_city_name", "chave_sem_espacos", "normalizar_texto"]

# Nome antigo mantido como apelido -- uma implementacao so, como manda o
# contrato: nenhuma logica de normalizacao vive neste arquivo.
normalize_city_name = normalizar_texto
