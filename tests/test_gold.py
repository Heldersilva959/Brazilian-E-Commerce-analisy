"""Integracao Gold: multiplos itens, enderecos, ausencias e publicacao atomica."""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import duckdb

from src.gold.dimensional import executar
from src.silver.contrato_gold import ENTRADAS, colunas


class GoldTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.silver = self.raiz / 'silver'
        self.gold = self.raiz / 'gold'
        self.silver.mkdir()
        self.con = duckdb.connect()
        self.addCleanup(self.con.close)
        for tabela in ENTRADAS:
            campos = ', '.join(f'"{nome}" {tipo}' for nome,tipo,_ in colunas(tabela))
            self.con.execute(f'CREATE TABLE {tabela}({campos})')
        self.inserir('clientes', customer_id='c1', customer_unique_id='pessoa', uf='SP')
        self.inserir('clientes', customer_id='c2', customer_unique_id='pessoa', uf='SP')
        self.inserir('clientes_municipios', customer_id='c1', cod_ibge='0000001', metodo_match='exato')
        self.inserir('clientes_municipios', customer_id='c2', metodo_match='nao_resolvido', motivo_nao_resolvido='sem coordenadas')
        self.inserir('geografia_integrada', cod_ibge='0000001', municipio='Cidade', municipio_normalizado='cidade', uf='SP', porte_municipio='Pequeno')
        self.inserir('vendedores', seller_id='v1', uf='SP')
        self.inserir('vendedores_municipios', seller_id='v1', cod_ibge='0000001', metodo_match='exato')
        self.inserir('produtos', product_id='pr1', categoria_produto='cat', categoria_produto_ingles='cat', peso_g=1000)
        self.inserir('pedidos', order_id='o1', customer_id='c1', status_pedido='delivered', ts_compra='2015-12-30', ts_entrega_cliente='2016-01-02', dias_ate_entrega=3, dias_atraso=-1, flag_atraso=False)
        self.inserir('pedidos', order_id='o2', customer_id='c2', status_pedido='delivered', ts_compra='2018-01-01', flag_entrega_ausente=True)
        self.inserir('pedidos', order_id='o3', customer_id='c1', status_pedido='canceled')
        for item,valor in [(1,10),(2,20)]:
            self.inserir('itens_pedido', order_id='o1', item_pedido_id=item, product_id='pr1', seller_id='v1', preco_produto=valor, valor_frete=1, valor_total_item=valor+1)
            self.inserir('distancias_itens', order_id='o1', order_item_id=item, distancia_km=42, flag_distancia_calculada=True)
        self.inserir('itens_pedido', order_id='o2', item_pedido_id=1, preco_produto=7)
        self.inserir('distancias_itens', order_id='o2', order_item_id=1, motivo_distancia_ausente='sem coordenadas')
        self.inserir('pagamentos', order_id='o1', tipo_pagamento_predominante='credit_card', parcelas_tipo_predominante=3, valor_total_pago=32, qtd_transacoes=2, qtd_metodos_distintos=1)
        self.inserir('avaliacoes', order_id='o1', review_id='r1', nota_review=5)
        self.exportar()

    def inserir(self,tabela,**valores):
        for nome,tipo,nulo in colunas(tabela):
            if not nulo and nome not in valores:
                valores[nome] = False if tipo=='BOOLEAN' else (0 if tipo in ('INTEGER','BIGINT') else '')
        campos = ','.join(valores)
        self.con.execute(f'INSERT INTO {tabela}({campos}) VALUES ({",".join("?" for _ in valores)})',list(valores.values()))

    def exportar(self):
        for tabela in ENTRADAS:
            self.con.sql(f'SELECT * FROM {tabela} ORDER BY ALL DESC').write_parquet(str(self.silver/f'{tabela}.parquet'))

    def test_carga_e_repeticao(self):
        executar(self.silver,self.gold)
        with duckdb.connect(str(self.gold/'dw.duckdb'),read_only=True) as dw:
            self.assertEqual(len(dw.execute('SHOW TABLES').fetchall()),8)
            self.assertEqual(dw.execute('SELECT count(*) FROM dim_cliente').fetchone()[0],2)
            self.assertEqual(dw.execute('SELECT quantidade_itens,valor_total_pedido,valor_total_pago,nota_avaliacao FROM fato_pedido WHERE order_id=\'o1\'').fetchone(),(2,Decimal('32'),Decimal('32'),5))
            self.assertEqual(dw.execute("SELECT quantidade_itens,valor_total_pedido,nota_avaliacao FROM fato_pedido WHERE order_id='o3'").fetchone(),(0,Decimal('0'),None))
            self.assertEqual(dw.execute("SELECT sk_geo_cliente,sk_tempo_entrega,sk_pagamento,valor_total_pedido FROM fato_pedido WHERE order_id='o2'").fetchone(),(0,0,0,None))
            self.assertEqual(dw.execute("SELECT sk_produto,sk_vendedor,distancia_km FROM fato_item_pedido WHERE order_id='o2'").fetchone(),(0,0,None))
            self.assertEqual(str(dw.execute('SELECT min(data_completa) FROM dim_tempo').fetchone()[0]),'2015-12-30')
        antes=json.loads((self.gold/'qualidade.json').read_text())['assinaturas']
        executar(self.silver,self.gold)
        depois=json.loads((self.gold/'qualidade.json').read_text())['assinaturas']
        self.assertEqual(antes,depois)

    def test_falha_preserva_dw(self):
        executar(self.silver,self.gold)
        antes=hashlib.sha256((self.gold/'dw.duckdb').read_bytes()).hexdigest()
        self.con.execute("UPDATE itens_pedido SET product_id='inexistente' WHERE order_id='o1'")
        self.exportar()
        with self.assertRaisesRegex(ValueError,'referencias inexistentes'):
            executar(self.silver,self.gold)
        self.assertEqual(antes,hashlib.sha256((self.gold/'dw.duckdb').read_bytes()).hexdigest())


if __name__=='__main__':
    unittest.main()
