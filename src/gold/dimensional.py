"""Carga completa e atomica do DW. Nao altera a Silver nem o DW anterior em falhas."""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import duckdb
from ..silver.contrato_gold import ENTRADAS, verificar

RAIZ = Path(__file__).resolve().parents[2]
DIR_SILVER = RAIZ / 'data/silver'
DIR_GOLD = RAIZ / 'data/gold'
SQL_DIR = Path(__file__).parent
log = logging.getLogger('gold')


def registrar_entradas(con, diretorio):
    erros = verificar(con, diretorio)
    if erros:
        raise ValueError('Contrato Silver -> Gold invalido:\n' + '\n'.join(erros))
    # Snapshot local: todos os joins e verificacoes leem as mesmas entradas.
    for nome in ENTRADAS:
        con.read_parquet(str(diretorio / f'{nome}.parquet')).create(f'slv_{nome}')


def validar_referencias(con):
    """Nulo legitimo usa desconhecido; referencia nao nula inexistente e erro."""
    referencias = [
        ('pedidos', 'customer_id', 'clientes', 'customer_id'),
        ('itens_pedido', 'order_id', 'pedidos', 'order_id'),
        ('itens_pedido', 'product_id', 'produtos', 'product_id'),
        ('itens_pedido', 'seller_id', 'vendedores', 'seller_id'),
        ('pagamentos', 'order_id', 'pedidos', 'order_id'),
        ('avaliacoes', 'order_id', 'pedidos', 'order_id'),
        ('clientes_municipios', 'cod_ibge', 'geografia_integrada', 'cod_ibge'),
        ('vendedores_municipios', 'cod_ibge', 'geografia_integrada', 'cod_ibge'),
    ]
    for origem, fk, destino, pk in referencias:
        n = con.execute(f'''SELECT count(*) FROM slv_{origem} o
            LEFT JOIN slv_{destino} d ON o.{fk}=d.{pk}
            WHERE o.{fk} IS NOT NULL AND d.{pk} IS NULL''').fetchone()[0]
        if n:
            raise ValueError(f'{origem}.{fk}: {n} referencias inexistentes em {destino}')
    for origem, destino, chave in (
        ('clientes', 'clientes_municipios', 'customer_id'),
        ('vendedores', 'vendedores_municipios', 'seller_id'),
    ):
        n = con.execute(f'''SELECT count(*) FROM slv_{origem} o FULL JOIN slv_{destino} d USING({chave})
            WHERE o.{chave} IS NULL OR d.{chave} IS NULL''').fetchone()[0]
        if n:
            raise ValueError(f'Cobertura incompleta: {origem} / {destino}: {n}')
    n = con.execute('''SELECT count(*) FROM slv_itens_pedido i FULL JOIN slv_distancias_itens d
        ON i.order_id=d.order_id AND i.item_pedido_id=d.order_item_id
        WHERE i.order_id IS NULL OR d.order_id IS NULL''').fetchone()[0]
    if n:
        raise ValueError(f'Cobertura de distancias por item divergente: {n}')


def materializar(con):
    con.execute((SQL_DIR / 'schema.sql').read_text(encoding='utf-8-sig'))
    con.execute((SQL_DIR / 'carga.sql').read_text(encoding='utf-8-sig'))
    for tabela, coluna in con.execute('''SELECT table_name, unnest(constraint_column_names)
        FROM duckdb_constraints() WHERE constraint_type='FOREIGN KEY' ''').fetchall():
        con.execute(f'CREATE INDEX idx_{tabela}_{coluna} ON {tabela}({coluna})')


def executar(silver=None, gold=None):
    from .qualidade import analisar, gravar_relatorio
    silver = Path(silver) if silver is not None else DIR_SILVER
    gold = Path(gold) if gold is not None else DIR_GOLD
    gold.mkdir(parents=True, exist_ok=True)
    destino = gold / 'dw.duckdb'
    with tempfile.TemporaryDirectory(prefix='carga_', dir=gold) as pasta:
        novo = Path(pasta) / 'dw.duckdb'
        with duckdb.connect(str(novo)) as con:
            log.info("Validando e copiando as onze entradas Silver")
            registrar_entradas(con, silver)
            validar_referencias(con)
            con.execute('BEGIN TRANSACTION')
            log.info("Criando dimensoes, fatos e indices")
            materializar(con)
            log.info("Validando integridade e reconciliacao")
            relatorio = analisar(con)
            if relatorio['erros']:
                raise ValueError('Carga Gold reprovada: ' + '; '.join(relatorio['erros']))
            # Nenhum dado Silver permanece no banco entregue ao BI.
            for nome in ENTRADAS:
                con.execute(f'DROP TABLE slv_{nome}')
            con.execute('COMMIT')
            con.execute('CHECKPOINT')
        # replace no mesmo volume; banco em uso no Windows causa erro sem apaga-lo.
        os.replace(novo, destino)
    gravar_relatorio(relatorio, gold)
    log.info('DW publicado em %s: %s', destino, relatorio['contagens'])
    return [{'tabela': t, 'linhas_entrada': None, 'linhas_saida': n}
            for t, n in relatorio['contagens'].items()]


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executar()
