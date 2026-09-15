"""Integracao geografica: liga cliente e vendedor ao municipio do IBGE.

Etapa do membro 3. Consome a silver (contrato de dados, secao 5.2) e nao le a
bronze nem os CSV originais:

    silver/municipios.parquet          cadastro canonico IBGE + SIDRA
    silver/geolocalizacao_cep.parquet  mediana de lat/lng por prefixo de CEP
    silver/clientes.parquet            customer_id, cep_prefixo, cidade, uf
    silver/vendedores.parquet          seller_id, cep_prefixo, cidade, uf
    silver/pedidos.parquet             para ligar item -> cliente
    silver/itens_pedido.parquet        grao das distancias por item
    de_para_municipios.csv             correcoes manuais, com evidencia

Ordem dos metodos de match, por entidade (secao 5.4):

    1. exato        nome normalizado + UF identicos ao IBGE
       exato        2a passada, mesma chave sem espacos, so quando unica na UF
    2. de_para      correcao manual versionada, com justificativa
    3. geografico   centroide municipal mais proximo na mesma UF, ate 50 km
    4. nao_resolvido

O de-para vem antes do fallback geografico de proposito: e evidencia
verificada (nome oficial, distrito de qual municipio), enquanto o geografico e
uma inferencia por proximidade. Deixar o geografico na frente faria uma
estimativa sobrepor um fato conferido.

Os centroides municipais sao formados **apenas** com prefixos de CEP
resolvidos pelo metodo exato, para o fallback nao realimentar o proprio erro.

### Interface consolidada

`docs/contrato_entrada_gold.md` v2 define os onze arquivos oficiais da Gold.
As saidas municipios_cliente/municipios_vendedor e distancias_vendedor_cliente
continuam como auxiliares de auditoria. A distancia por par usa pontos
municipais; a distancia oficial por item usa CEPs, e os valores nao sao equivalentes.

Execucao:

    .venv\\Scripts\\python.exe -m src.silver.integracao_municipios
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import duckdb

from ..utils.normalizacao import registrar_no_duckdb

RAIZ = Path(__file__).resolve().parents[2]
DIR_SILVER = RAIZ / "data" / "silver"
DIR_DOCS = RAIZ / "docs"
DE_PARA = RAIZ / "de_para_municipios.csv"

SILVER_ESPERADA: dict[str, Path] = {
    "municipios": DIR_SILVER / "municipios.parquet",
    "geolocalizacao_cep": DIR_SILVER / "geolocalizacao_cep.parquet",
    "clientes": DIR_SILVER / "clientes.parquet",
    "vendedores": DIR_SILVER / "vendedores.parquet",
    "pedidos": DIR_SILVER / "pedidos.parquet",
    "itens_pedido": DIR_SILVER / "itens_pedido.parquet",
}

# Aceite do fallback geografico (contrato de dados, secao 5.4). Acima disso o
# caso fica como nao resolvido -- e melhor um municipio nulo do que um errado.
RAIO_ACEITE_KM = 50.0

log = logging.getLogger("integracao_municipios")


def _requeridos() -> dict[str, Path]:
    faltando = [(n, p) for n, p in SILVER_ESPERADA.items() if not p.exists()]
    if faltando:
        detalhes = "; ".join(f"{n} -> {p}" for n, p in faltando)
        raise FileNotFoundError(
            f"Arquivo(s) da silver ausente(s) para a integracao: {detalhes}. "
            "Rode a etapa silver antes (python -m src.silver.transform)."
        )
    return SILVER_ESPERADA


def _gravar(con: duckdb.DuckDBPyConnection, sql: str, destino: Path) -> int:
    DIR_SILVER.mkdir(parents=True, exist_ok=True)
    formato = "CSV, HEADER" if destino.suffix == ".csv" else "PARQUET"
    con.execute(f"COPY ({sql}) TO '{destino.as_posix()}' (FORMAT {formato})")
    total = con.execute(f"SELECT count(*) FROM ({sql})").fetchone()[0]
    log.info("gravado %s (%d linhas)", destino.relative_to(RAIZ), total)
    return total


def preparar_referencia(con: duckdb.DuckDBPyConnection) -> None:
    """Monta o cadastro municipal, as coordenadas por CEP e o de-para."""
    arq = _requeridos()

    con.execute(
        """
        create or replace macro haversine_km(lat1, lng1, lat2, lng2) as
            6371.0088 * 2 * asin(sqrt(
                pow(sin(radians(lat2 - lat1) / 2), 2)
                + cos(radians(lat1)) * cos(radians(lat2))
                  * pow(sin(radians(lng2 - lng1) / 2), 2)
            ));
        """
    )

    # Cadastro municipal com as duas chaves de comparacao. `chave_unica_na_uf`
    # protege a 2a passada: se duas cidades da mesma UF colapsarem na mesma
    # chave sem espacos, nenhuma das duas pode ser usada para casar.
    con.execute(
        f"""
        create or replace table municipios_ref as
        with base as (
            select
                cod_ibge,
                municipio,
                municipio_normalizado,
                chave_sem_espacos(municipio) as chave_sem_espaco,
                uf,
                nome_uf,
                regiao,
                populacao,
                pib_per_capita,
                ano_referencia_indicadores,
                porte_municipio
            from read_parquet('{arq["municipios"].as_posix()}')
        )
        select
            *,
            count(*) over (partition by uf, chave_sem_espaco) = 1 as chave_unica_na_uf
        from base
        """
    )

    con.execute(
        f"""
        create or replace table coord_cep as
        select
            cep_prefixo,
            latitude_mediana as latitude,
            longitude_mediana as longitude
        from read_parquet('{arq["geolocalizacao_cep"].as_posix()}')
        where latitude_mediana is not null and longitude_mediana is not null
        """
    )

    # De-para manual. Lido como texto para o codigo do IBGE nao virar numero e
    # perder o zero a esquerda. Linhas que apontem para codigo inexistente sao
    # erro de preenchimento e derrubam a etapa.
    if DE_PARA.exists():
        con.execute(
            f"""
            create or replace table de_para as
            select
                normalizar_texto(cidade_origem) as cidade_normalizada,
                upper(trim(uf_origem)) as uf,
                trim(cod_ibge) as cod_ibge,
                justificativa
            from read_csv('{DE_PARA.as_posix()}', header = true, all_varchar = true)
            where nullif(trim(cod_ibge), '') is not null
            """
        )
    else:
        con.execute(
            "create or replace table de_para as "
            "select '' as cidade_normalizada, '' as uf, '' as cod_ibge, "
            "'' as justificativa where false"
        )

    invalidos = con.execute(
        """
        select d.cidade_normalizada, d.uf, d.cod_ibge
        from de_para d
        left join municipios_ref m on m.cod_ibge = d.cod_ibge
        where m.cod_ibge is null
        """
    ).fetchall()
    if invalidos:
        raise ValueError(
            f"de_para_municipios.csv aponta para cod_ibge inexistente: {invalidos}"
        )

    duplicados = con.execute(
        "select cidade_normalizada, uf, count(*) from de_para "
        "group by 1, 2 having count(*) > 1"
    ).fetchall()
    if duplicados:
        raise ValueError(
            f"de_para_municipios.csv tem (cidade, uf) repetido: {duplicados}"
        )

    n_de_para = con.execute("select count(*) from de_para").fetchone()[0]
    log.info("de-para manual carregado: %d entrada(s)", n_de_para)


def resolver_prefixos_cep(con: duckdb.DuckDBPyConnection) -> None:
    """Resolve o prefixo de CEP pelo nome e forma os centroides municipais.

    O centroide sai da mediana das coordenadas dos prefixos resolvidos **so**
    pelo metodo exato, como manda a secao 5.4: um prefixo resolvido por
    aproximacao nao pode entrar na formacao do ponto que sera usado para
    aproximar os proximos.
    """
    arq = _requeridos()

    con.execute(
        f"""
        create or replace table cep_exato as
        with prefixo as (
            select
                cep_prefixo,
                normalizar_texto(cidade_predominante) as cidade_normalizada,
                chave_sem_espacos(cidade_predominante) as chave_sem_espaco,
                uf_predominante as uf,
                latitude_mediana as latitude,
                longitude_mediana as longitude
            from read_parquet('{arq["geolocalizacao_cep"].as_posix()}')
            where cidade_predominante is not null
              and latitude_mediana is not null
        ),
        por_nome as (
            select p.*, m.cod_ibge
            from prefixo p
            left join municipios_ref m
              on m.uf = p.uf and m.municipio_normalizado = p.cidade_normalizada
        ),
        por_chave as (
            select
                p.cep_prefixo, p.uf, p.latitude, p.longitude,
                coalesce(p.cod_ibge, m.cod_ibge) as cod_ibge
            from por_nome p
            left join municipios_ref m
              on p.cod_ibge is null
             and m.uf = p.uf
             and m.chave_sem_espaco = p.chave_sem_espaco
             and m.chave_unica_na_uf
        )
        select * from por_chave where cod_ibge is not null
        """
    )

    con.execute(
        """
        create or replace table centroides as
        select
            cod_ibge,
            uf,
            median(latitude) as latitude_representativa,
            median(longitude) as longitude_representativa,
            count(*) as qtd_prefixos
        from cep_exato
        group by cod_ibge, uf
        """
    )

    n_cep, n_centroide = con.execute(
        "select (select count(*) from cep_exato), (select count(*) from centroides)"
    ).fetchone()
    log.info(
        "prefixos de CEP resolvidos por nome: %d | municipios com centroide: %d",
        n_cep,
        n_centroide,
    )


def resolver_entidade(con: duckdb.DuckDBPyConnection, entidade: str) -> str:
    """Aplica os quatro metodos a clientes ou vendedores, nessa ordem.

    Devolve o nome da tabela criada, com uma linha por id -- a unicidade e
    condicao de aceite do contrato e e conferida no fim da etapa.
    """
    arq = _requeridos()
    if entidade == "clientes":
        chave, fonte = "customer_id", arq["clientes"]
    else:
        chave, fonte = "seller_id", arq["vendedores"]

    tabela = f"mapa_{entidade}"
    con.execute(
        f"""
        create or replace table {tabela} as
        with base as (
            select
                {chave} as id_entidade,
                cep_prefixo,
                cidade as cidade_original,
                normalizar_texto(cidade) as cidade_normalizada,
                chave_sem_espacos(cidade) as chave_sem_espaco,
                uf
            from read_parquet('{fonte.as_posix()}')
        ),
        -- 1. nome normalizado identico dentro da UF
        passo_exato as (
            select b.*, m.cod_ibge as cod_exato
            from base b
            left join municipios_ref m
              on m.uf = b.uf and m.municipio_normalizado = b.cidade_normalizada
        ),
        -- 1b. mesma chave ignorando espacos, so quando unica na UF
        passo_chave as (
            select p.*, m.cod_ibge as cod_chave
            from passo_exato p
            left join municipios_ref m
              on p.cod_exato is null
             and m.uf = p.uf
             and m.chave_sem_espaco = p.chave_sem_espaco
             and m.chave_unica_na_uf
        ),
        -- 2. de-para manual, com evidencia registrada
        passo_de_para as (
            select p.*, d.cod_ibge as cod_de_para
            from passo_chave p
            left join de_para d
              on p.cod_exato is null
             and p.cod_chave is null
             and d.uf = p.uf
             and d.cidade_normalizada = p.cidade_normalizada
        ),
        -- 3. centroide municipal mais proximo, na mesma UF, ate o raio aceito
        pendente_geo as (
            select distinct p.cep_prefixo, p.uf
            from passo_de_para p
            where p.cod_exato is null and p.cod_chave is null and p.cod_de_para is null
        ),
        candidatos as (
            select
                pg.cep_prefixo,
                pg.uf,
                c.cod_ibge,
                haversine_km(
                    g.latitude, g.longitude,
                    c.latitude_representativa, c.longitude_representativa
                ) as distancia_km,
                row_number() over (
                    partition by pg.cep_prefixo, pg.uf
                    order by haversine_km(
                        g.latitude, g.longitude,
                        c.latitude_representativa, c.longitude_representativa
                    ) asc, c.cod_ibge asc
                ) as posicao
            from pendente_geo pg
            join coord_cep g on g.cep_prefixo = pg.cep_prefixo
            join centroides c on c.uf = pg.uf
        ),
        geo as (
            select cep_prefixo, uf, cod_ibge, distancia_km
            from candidatos
            where posicao = 1 and distancia_km <= {RAIO_ACEITE_KM}
        ),
        consolidado as (
            select
                p.id_entidade,
                p.cep_prefixo,
                p.cidade_original,
                p.cidade_normalizada,
                p.uf,
                coalesce(p.cod_exato, p.cod_chave, p.cod_de_para, g.cod_ibge) as cod_ibge,
                case
                    when p.cod_exato is not null or p.cod_chave is not null then 'exato'
                    when p.cod_de_para is not null then 'de_para'
                    when g.cod_ibge is not null then 'geografico'
                    else 'nao_resolvido'
                end as metodo_match,
                case when p.cod_exato is null and p.cod_chave is null
                      and p.cod_de_para is null then g.distancia_km end as distancia_match_km,
                cc.latitude,
                cc.longitude,
                (g.cep_prefixo is null and cc.cep_prefixo is null) as sem_coordenada
            from passo_de_para p
            left join geo g on g.cep_prefixo = p.cep_prefixo and g.uf = p.uf
            left join coord_cep cc on cc.cep_prefixo = p.cep_prefixo
        )
        select
            id_entidade,
            cep_prefixo,
            cidade_original,
            cidade_normalizada,
            uf,
            cod_ibge,
            metodo_match,
            cast(distancia_match_km as decimal(10, 2)) as distancia_match_km,
            latitude,
            longitude,
            case
                when cod_ibge is not null then null
                when latitude is null then 'prefixo de CEP sem coordenada valida'
                else 'sem nome correspondente no IBGE e nenhum centroide a ate '
                     || {RAIO_ACEITE_KM} || ' km na UF'
            end as motivo_nao_resolvido
        from consolidado
        """
    )

    resumo = con.execute(
        f"select metodo_match, count(*) from {tabela} group by 1 order by 2 desc"
    ).fetchall()
    log.info("%s: %s", entidade, ", ".join(f"{m}={n}" for m, n in resumo))
    return tabela


def gravar_mapeamentos(con: duckdb.DuckDBPyConnection) -> None:
    """Grava a interface Gold v2 e os auxiliares de auditoria."""
    for entidade, chave in (("clientes", "customer_id"), ("vendedores", "seller_id")):
        tabela = f"mapa_{entidade}"
        sufixo = "cliente" if entidade == "clientes" else "vendedor"

        # Formato de docs/contratos_dados.md secao 5.3 (vocabulario: de_para).
        _gravar(
            con,
            f"""
            select
                id_entidade as {chave},
                cod_ibge,
                metodo_match,
                distancia_match_km
            from {tabela}
            order by {chave}
            """,
            DIR_SILVER / f"municipios_{sufixo}.parquet",
        )

        # Formato de docs/contrato_entrada_gold.md secoes 12 e 13, que pede
        # mais colunas e chama o de-para de "manual".
        _gravar(
            con,
            f"""
            select
                id_entidade as {chave},
                cod_ibge,
                case when metodo_match = 'de_para' then 'manual' else metodo_match end
                    as metodo_match,
                cast(distancia_match_km as double) as distancia_match_km,
                latitude as latitude_{sufixo},
                longitude as longitude_{sufixo},
                cidade_original,
                cidade_normalizada,
                uf,
                motivo_nao_resolvido
            from {tabela}
            order by {chave}
            """,
            DIR_SILVER / f"{entidade}_municipios.parquet",
        )

    # Cadastro municipal com o ponto representativo (contrato da gold, secao 11).
    _gravar(
        con,
        """
        select
            m.cod_ibge,
            m.municipio,
            m.municipio_normalizado,
            m.uf,
            m.nome_uf,
            m.regiao,
            m.populacao as populacao_estimada,
            m.pib_per_capita,
            m.ano_referencia_indicadores,
            m.porte_municipio,
            c.latitude_representativa,
            c.longitude_representativa
        from municipios_ref m
        left join centroides c on c.cod_ibge = m.cod_ibge
        order by m.cod_ibge
        """,
        DIR_SILVER / "geografia_integrada.parquet",
    )


def gravar_distancias(con: duckdb.DuckDBPyConnection) -> None:
    """Distancia oficial por item (CEP) e auxiliar por par (municipio)."""
    arq = _requeridos()

    # Par (seller_id, customer_id) -- contrato de dados, secao 5.3: Haversine
    # entre os centroides municipais resolvidos.
    _gravar(
        con,
        f"""
        with pares as (
            select distinct i.seller_id, p.customer_id
            from read_parquet('{arq["itens_pedido"].as_posix()}') i
            join read_parquet('{arq["pedidos"].as_posix()}') p on p.order_id = i.order_id
        )
        select
            pr.seller_id,
            pr.customer_id,
            cast(haversine_km(
                cv.latitude_representativa, cv.longitude_representativa,
                cc.latitude_representativa, cc.longitude_representativa
            ) as decimal(10, 2)) as distancia_km,
            (mv.metodo_match <> 'exato' or mc.metodo_match <> 'exato')
                as flag_distancia_estimada
        from pares pr
        left join mapa_vendedores mv on mv.id_entidade = pr.seller_id
        left join mapa_clientes mc on mc.id_entidade = pr.customer_id
        left join centroides cv on cv.cod_ibge = mv.cod_ibge
        left join centroides cc on cc.cod_ibge = mc.cod_ibge
        order by pr.seller_id, pr.customer_id
        """,
        DIR_SILVER / "distancias_vendedor_cliente.parquet",
    )

    # Grao item -- contrato da gold, secao 14: distancia entre as medianas dos
    # prefixos de CEP do cliente e do vendedor, nao entre centroides.
    _gravar(
        con,
        f"""
        with itens as (
            select i.order_id, i.item_pedido_id as order_item_id, i.seller_id, p.customer_id
            from read_parquet('{arq["itens_pedido"].as_posix()}') i
            join read_parquet('{arq["pedidos"].as_posix()}') p on p.order_id = i.order_id
        ),
        com_coord as (
            select
                it.*,
                gv.latitude as lat_vendedor, gv.longitude as lng_vendedor,
                gc.latitude as lat_cliente, gc.longitude as lng_cliente
            from itens it
            left join mapa_vendedores mv on mv.id_entidade = it.seller_id
            left join mapa_clientes mc on mc.id_entidade = it.customer_id
            left join coord_cep gv on gv.cep_prefixo = mv.cep_prefixo
            left join coord_cep gc on gc.cep_prefixo = mc.cep_prefixo
        )
        select
            order_id,
            order_item_id,
            haversine_km(lat_vendedor, lng_vendedor, lat_cliente, lng_cliente)
                as distancia_km,
            (lat_vendedor is not null and lat_cliente is not null)
                as flag_distancia_calculada,
            case
                when lat_vendedor is null and lat_cliente is null
                    then 'prefixo de CEP do vendedor e do cliente sem coordenada valida'
                when lat_vendedor is null then 'prefixo de CEP do vendedor sem coordenada valida'
                when lat_cliente is null then 'prefixo de CEP do cliente sem coordenada valida'
            end as motivo_distancia_ausente
        from com_coord
        order by order_id, order_item_id
        """,
        DIR_SILVER / "distancias_itens.parquet",
    )


def conferir_aceite(con: duckdb.DuckDBPyConnection) -> None:
    """Condicoes de aceite do contrato, verificadas antes de declarar sucesso.

    Uma linha duplicada em qualquer um dos mapeamentos multiplica itens na
    fato e quebra o faturamento em silencio -- por isso a etapa falha aqui em
    vez de entregar o arquivo.
    """
    checagens = [
        (
            "municipios_cliente: 1 linha por customer_id",
            "select count(*) from (select customer_id from "
            f"read_parquet('{(DIR_SILVER / 'municipios_cliente.parquet').as_posix()}') "
            "group by 1 having count(*) > 1)",
        ),
        (
            "municipios_vendedor: 1 linha por seller_id",
            "select count(*) from (select seller_id from "
            f"read_parquet('{(DIR_SILVER / 'municipios_vendedor.parquet').as_posix()}') "
            "group by 1 having count(*) > 1)",
        ),
        (
            "distancias_itens: 1 linha por (order_id, order_item_id)",
            "select count(*) from (select order_id, order_item_id from "
            f"read_parquet('{(DIR_SILVER / 'distancias_itens.parquet').as_posix()}') "
            "group by 1, 2 having count(*) > 1)",
        ),
        (
            "cod_ibge sempre existente no cadastro do IBGE",
            "select count(*) from mapa_clientes m "
            "left join municipios_ref r on r.cod_ibge = m.cod_ibge "
            "where m.cod_ibge is not null and r.cod_ibge is null",
        ),
        (
            "distancia_match_km so no metodo geografico",
            "select count(*) from mapa_clientes "
            "where distancia_match_km is not null and metodo_match <> 'geografico'",
        ),
        (
            "fallback geografico dentro do raio aceito",
            "select count(*) from mapa_clientes "
            f"where metodo_match = 'geografico' and distancia_match_km > {RAIO_ACEITE_KM}",
        ),
    ]
    falhas = [(nome, con.execute(sql).fetchone()[0]) for nome, sql in checagens]
    falhas = [(nome, n) for nome, n in falhas if n]
    if falhas:
        detalhe = "; ".join(f"{nome}: {n} ocorrencia(s)" for nome, n in falhas)
        raise ValueError(f"condicoes de aceite da integracao violadas -- {detalhe}")
    log.info("condicoes de aceite: %d checagens, todas sem ocorrencia", len(checagens))


def _estatisticas(con: duckdb.DuckDBPyConnection) -> dict:
    dados: dict = {}
    for entidade, rotulo in (("clientes", "clientes"), ("vendedores", "vendedores")):
        linhas = dict(
            con.execute(
                f"select metodo_match, count(*) from mapa_{entidade} group by 1"
            ).fetchall()
        )
        total = sum(linhas.values())
        resolvidos = total - linhas.get("nao_resolvido", 0)
        dados[f"total_{rotulo}"] = total
        dados[f"{rotulo}_match_exato"] = linhas.get("exato", 0)
        dados[f"{rotulo}_match_geografico"] = linhas.get("geografico", 0)
        dados[f"{rotulo}_match_manual"] = linhas.get("de_para", 0)
        dados[f"{rotulo}_nao_resolvidos"] = linhas.get("nao_resolvido", 0)
        dados[f"taxa_match_{rotulo}"] = round(resolvidos / total, 6) if total else 0.0
    return dados


def gravar_relatorios(con: duckdb.DuckDBPyConnection) -> dict:
    """JSON de qualidade, CSV dos nao resolvidos e o relatorio de match."""
    dados = _estatisticas(con)

    destino_json = DIR_SILVER / "qualidade_integracao_municipios.json"
    destino_json.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("gravado %s", destino_json.relative_to(RAIZ))

    _gravar(
        con,
        """
        select 'cliente' as entidade, cidade_original, cidade_normalizada, uf,
               count(*) as qtd_entidades, any_value(motivo_nao_resolvido) as motivo
        from mapa_clientes where cod_ibge is null
        group by 1, 2, 3, 4
        union all
        select 'vendedor', cidade_original, cidade_normalizada, uf,
               count(*), any_value(motivo_nao_resolvido)
        from mapa_vendedores where cod_ibge is null
        group by 1, 2, 3, 4
        order by qtd_entidades desc, uf, cidade_normalizada
        """,
        DIR_SILVER / "municipios_nao_resolvidos.csv",
    )

    nao_resolvidos = con.execute(
        """
        select entidade, cidade_original, uf, qtd from (
            select 'cliente' as entidade, cidade_original, uf, count(*) as qtd
            from mapa_clientes where cod_ibge is null group by 1, 2, 3
            union all
            select 'vendedor', cidade_original, uf, count(*)
            from mapa_vendedores where cod_ibge is null group by 1, 2, 3
        ) order by qtd desc, uf, cidade_original
        """
    ).fetchall()

    de_para_aplicado = con.execute(
        """
        with aplicado as (
            select
                d.cidade_normalizada, d.uf, d.cod_ibge, m.municipio, d.justificativa,
                (select count(*) from mapa_clientes c
                  where c.metodo_match = 'de_para'
                    and c.cidade_normalizada = d.cidade_normalizada and c.uf = d.uf) as clientes,
                (select count(*) from mapa_vendedores v
                  where v.metodo_match = 'de_para'
                    and v.cidade_normalizada = d.cidade_normalizada and v.uf = d.uf) as vendedores
            from de_para d
            join municipios_ref m on m.cod_ibge = d.cod_ibge
        )
        select cidade_normalizada, uf, cod_ibge, municipio, justificativa, clientes, vendedores
        from aplicado
        order by clientes + vendedores desc, uf, cidade_normalizada
        """
    ).fetchall()

    _escrever_relatorio_match(dados, nao_resolvidos, de_para_aplicado)
    return dados


def _milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _percentual(parte: int, total: int) -> str:
    return f"{parte / total:.2%}".replace(".", ",") if total else "0,00%"


def _escrever_relatorio_match(dados: dict, nao_resolvidos: list, de_para: list) -> None:
    def bloco(rotulo: str) -> str:
        total = dados[f"total_{rotulo}"]
        metodos = [
            ("exato", dados[f"{rotulo}_match_exato"]),
            ("de_para (manual)", dados[f"{rotulo}_match_manual"]),
            ("geografico", dados[f"{rotulo}_match_geografico"]),
            ("nao_resolvido", dados[f"{rotulo}_nao_resolvidos"]),
        ]
        linhas = [
            f"| {nome} | {_milhar(qtd)} | {_percentual(qtd, total)} |" for nome, qtd in metodos
        ]
        linhas.append(f"| **total** | **{_milhar(total)}** | **100,00%** |")
        return "\n".join(linhas)

    partes = [
        "# Relatório de match — integração geográfica",
        "",
        "Gerado por `src/silver/integracao_municipios.py`. Não editar à mão:",
        "os números são reescritos a cada execução.",
        "",
        "## Taxa por método",
        "",
        "### Clientes",
        "",
        "| Método | Registros | Participação |",
        "|---|---:|---:|",
        bloco("clientes"),
        "",
        "Taxa global de resolução: **"
        + f"{dados['taxa_match_clientes']:.2%}".replace(".", ",") + "**",
        "",
        "### Vendedores",
        "",
        "| Método | Registros | Participação |",
        "|---|---:|---:|",
        bloco("vendedores"),
        "",
        "Taxa global de resolução: **"
        + f"{dados['taxa_match_vendedores']:.2%}".replace(".", ",") + "**",
        "",
        "## De-para manual aplicado",
        "",
    ]

    if de_para:
        partes += [
            "| Cidade no Olist | UF | cod_ibge | Município oficial | Clientes | Vendedores | Evidência |",
            "|---|---|---|---|---:|---:|---|",
        ]
        for cidade, uf, cod, municipio, just, n_cli, n_ven in de_para:
            partes.append(
                f"| {cidade} | {uf} | {cod} | {municipio} | {n_cli} | {n_ven} | {just} |"
            )
    else:
        partes.append("Nenhuma entrada preenchida em `de_para_municipios.csv`.")

    partes += [
        "",
        "## Não resolvidos",
        "",
    ]
    if nao_resolvidos:
        partes += [
            f"{len(nao_resolvidos)} combinação(ões) de cidade e UF sem município. "
            "Lista completa:",
            "",
            "| Entidade | Cidade no Olist | UF | Registros |",
            "|---|---|---|---:|",
        ]
        for entidade, cidade, uf, qtd in nao_resolvidos:
            partes.append(f"| {entidade} | {cidade} | {uf} | {qtd} |")
    else:
        partes.append("Nenhum. Todos os clientes e vendedores foram associados a um município.")

    partes += [
        "",
        "## Interface Silver → Gold v2",
        "",
        "O contrato oficial está em `docs/contrato_entrada_gold.md`.",
        "A Gold usa `clientes_municipios`, `vendedores_municipios`,",
        "`geografia_integrada` e `distancias_itens` como saídas da integração.",
        "Os demais Parquets desta etapa são auxiliares de auditoria.",
        "",
        "Os mapeamentos auxiliares usam `de_para`, equivalente a `manual` na interface.",
        "A distância por par usa pontos municipais; a distância por item usa CEPs.",
        "Essas distâncias não são equivalentes. A medida oficial da Gold é a distância por item.",
        "",
    ]

    destino = DIR_DOCS / "relatorio_match.md"
    destino.write_text("\n".join(partes) + "\n", encoding="utf-8")
    log.info("gravado %s", destino.relative_to(RAIZ))


def executar() -> None:
    """Ponto de entrada chamado por `src/run_pipeline.py`."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    con = duckdb.connect()
    registrar_no_duckdb(con)

    preparar_referencia(con)
    resolver_prefixos_cep(con)
    resolver_entidade(con, "clientes")
    resolver_entidade(con, "vendedores")
    gravar_mapeamentos(con)
    gravar_distancias(con)
    conferir_aceite(con)
    dados = gravar_relatorios(con)

    log.info(
        "taxa de resolucao: clientes %.2f%% | vendedores %.2f%%",
        dados["taxa_match_clientes"] * 100,
        dados["taxa_match_vendedores"] * 100,
    )


def main() -> None:
    executar()


if __name__ == "__main__":
    executar()
