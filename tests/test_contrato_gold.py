"""Regressoes de contrato e imputacao: dados artificiais apenas nos testes."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import duckdb
from src.silver.contrato_gold import ENTRADAS, colunas, verificar
from src.silver import transform


class ContratoGoldTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.con = duckdb.connect()
        self.addCleanup(self.con.close)
        for tabela in ENTRADAS:
            campos = ', '.join(f'CAST(NULL AS {tipo}) AS "{nome}"' for nome, tipo, _ in colunas(tabela))
            self.con.sql(f'SELECT {campos} WHERE FALSE').write_parquet(str(self.raiz / f'{tabela}.parquet'))

    def test_esquema_completo(self):
        self.assertEqual(verificar(self.con, self.raiz), [])

    def test_arquivo_ausente(self):
        (self.raiz / 'pedidos.parquet').unlink()
        self.assertTrue(any('Arquivo obrigatorio ausente' in e for e in verificar(self.con, self.raiz)))

    def test_tipo_nulo_e_duplicidade(self):
        self.con.sql("SELECT NULL::VARCHAR AS seller_id, 123::INTEGER AS cep_prefixo, 'cidade' AS cidade, 'SP' AS uf FROM range(2)").write_parquet(str(self.raiz / 'vendedores.parquet'))
        erros = verificar(self.con, self.raiz)
        self.assertTrue(any('esperado VARCHAR, encontrado INTEGER' in e for e in erros))
        self.assertTrue(any('2 nulos proibidos' in e for e in erros))
        self.assertTrue(any('chaves duplicadas' in e for e in erros))

    def test_coluna_ausente(self):
        self.con.sql("SELECT 'v1' AS seller_id").write_parquet(str(self.raiz / 'vendedores.parquet'))
        self.assertTrue(any('vendedores.cep_prefixo' in e and 'ausente' in e for e in verificar(self.con, self.raiz)))

    def test_imputacao_exige_suporte_por_medida(self):
        produtos = self.raiz / 'brz_produtos.parquet'
        traducao = self.raiz / 'brz_traducao.parquet'
        self.con.sql("""SELECT i::VARCHAR AS product_id, 'categoria' AS product_category_name,
            CASE WHEN i < 5 THEN '100' ELSE '' END AS product_weight_g,
            CASE WHEN i < 5 THEN '10' ELSE '' END AS product_length_cm,
            CASE WHEN i < 4 THEN '20' ELSE '' END AS product_height_cm,
            '' AS product_width_cm FROM range(6) t(i)""").write_parquet(str(produtos))
        self.con.sql("SELECT 'categoria' AS product_category_name, 'category' AS product_category_name_english").write_parquet(str(traducao))
        with patch.object(transform, 'RAIZ', self.raiz), patch.object(transform, 'DIR_SILVER', self.raiz), patch.object(transform, '_tabelas_requeridas', return_value={'produtos': produtos, 'traducao_categorias': traducao}):
            transform.transformar_produtos(self.con)
        saida = self.raiz / 'produtos.parquet'
        linha = self.con.read_parquet(str(saida)).filter("product_id = '5'").project('peso_g, comprimento_cm, altura_cm, largura_cm, flag_peso_imputado, flag_dimensoes_imputadas').fetchone()
        self.assertEqual(linha, (100.0, 10.0, None, None, True, True))
        linha = self.con.read_parquet(str(saida)).filter("product_id = '4'").project('flag_dimensoes_imputadas').fetchone()
        self.assertEqual(linha, (False,))


if __name__ == '__main__':
    unittest.main()
