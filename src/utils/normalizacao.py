"""Normalizacao de texto para os matches -- implementacao unica do grupo.

O contrato de dados (secao 5.1) fixa que existe uma so funcao de normalizacao
no repositorio e que o membro 3 e o dono dela. Qualquer camada que precise
comparar nome de municipio importa daqui; ninguem escreve uma segunda versao.

Passos de `normalizar_texto`, na ordem do contrato:

    minusculas -> NFKD e remocao dos combinantes (acentos) -> tudo que nao
    seja letra, numero ou espaco vira espaco -> colapso de espacos -> strip

O separador vira espaco em vez de sumir, e isso e deliberado: "Embu-Guacu"
resulta em "embu guacu" e "Santa Barbara d'Oeste" em "santa barbara d oeste",
que sao as formas que o Olist mais usa. Mas o Olist tambem escreve "embuguacu"
e "santa barbara doeste", e nenhuma regra unica de normalizacao casa as duas
grafias ao mesmo tempo. Por isso existe `chave_sem_espacos`, aplicada como
segunda passada do metodo exato: ver docs/relatorio_match.md.
"""

from __future__ import annotations

import re
import unicodedata

_NAO_ALFANUMERICO = re.compile(r"[^a-z0-9 ]")
_ESPACOS = re.compile(r"\s+")


def normalizar_texto(s: str | None) -> str:
    """Nome comparavel: sem acento, sem pontuacao, minusculo e sem espaco duplo.

    Recebe None e valores nao textuais sem quebrar -- a bronze entrega tudo
    como string, mas a coluna pode vir nula da silver.
    """
    if s is None or not isinstance(s, str):
        return ""

    texto = s.lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = _NAO_ALFANUMERICO.sub(" ", texto)
    texto = _ESPACOS.sub(" ", texto)
    return texto.strip()


def chave_sem_espacos(s: str | None) -> str:
    """Chave secundaria do metodo exato: o nome normalizado sem nenhum espaco.

    Existe para absorver a divergencia de separador entre as duas bases. O
    match por nome identico ja resolve a grafia com espaco; esta chave pega a
    outra metade:

        IBGE  "Santa Barbara d'Oeste" -> "santa barbara d oeste"
        Olist "santa barbara doeste"  -> "santa barbara doeste"
        chave -> "santabarbaradoeste" nos dois

        IBGE  "Embu-Guacu" -> "embu guacu"
        Olist "embuguacu"  -> "embuguacu"
        chave -> "embuguacu" nos dois

    So e aplicada sobre o residuo do match por nome identico, e so quando a
    chave for unica dentro da UF -- nunca para desempatar homonimos.
    """
    return normalizar_texto(s).replace(" ", "")


def registrar_no_duckdb(con) -> None:
    """Expoe as duas funcoes ao SQL do DuckDB.

    Assim a silver e a integracao normalizam pelo mesmo codigo Python, sem uma
    segunda implementacao escrita em SQL que possa divergir em silencio.
    """
    # null_handling="special": o DuckDB entrega o NULL a funcao em vez de
    # devolver NULL direto, e as duas tratam None como string vazia.
    con.create_function(
        "normalizar_texto", normalizar_texto, ["VARCHAR"], "VARCHAR", null_handling="special"
    )
    con.create_function(
        "chave_sem_espacos", chave_sem_espacos, ["VARCHAR"], "VARCHAR", null_handling="special"
    )
