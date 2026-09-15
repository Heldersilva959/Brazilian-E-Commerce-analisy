from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "dimensional"
OUT.mkdir(parents=True, exist_ok=True)
PDF = OUT / "diagrama_modelo_dimensional.pdf"

W, H = landscape(A3)
navy = colors.HexColor("#15333b")
teal = colors.HexColor("#2b817a")
mint = colors.HexColor("#d5f39b")
paper = colors.HexColor("#f6f7f2")
line = colors.HexColor("#91a9a4")
muted = colors.HexColor("#557078")
gold = colors.HexColor("#f0c36a")


def box(c, x, y, w, h, title, rows, fill, title_fill=None):
    c.setFillColor(fill)
    c.setStrokeColor(line)
    c.setLineWidth(1)
    c.roundRect(x, y, w, h, 8, stroke=1, fill=1)
    c.setFillColor(title_fill or navy)
    c.roundRect(x, y + h - 30, w, 30, 8, stroke=0, fill=1)
    c.rect(x, y + h - 30, w, 10, stroke=0, fill=1)
    c.setFillColor(colors.white if title_fill != mint else navy)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x + 12, y + h - 20, title)
    c.setFillColor(navy)
    c.setFont("Helvetica", 8.3)
    yy = y + h - 46
    for row in rows:
        c.drawString(x + 12, yy, row)
        yy -= 13
    return (x, y, w, h)


def center(pt):
    x, y, w, h = pt
    return x + w / 2, y + h / 2


def connect(c, a, b, color=teal):
    x1, y1 = center(a)
    x2, y2 = center(b)
    c.setStrokeColor(color)
    c.setLineWidth(1.4)
    c.line(x1, y1, x2, y2)
    # small arrow head at destination
    c.setFillColor(color)
    c.circle(x2, y2, 2.3, stroke=0, fill=1)


def main():
    c = canvas.Canvas(str(PDF), pagesize=(W, H))
    c.setTitle("Diagrama do modelo dimensional - Data Warehouse Olist")
    c.setAuthor("Projeto Data Warehouse de e-commerce brasileiro")
    c.setFillColor(paper)
    c.rect(0, 0, W, H, stroke=0, fill=1)

    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(42, H - 48, "Modelo dimensional | Data Warehouse de e-commerce brasileiro")
    c.setFillColor(muted)
    c.setFont("Helvetica", 10)
    c.drawString(43, H - 67, "Esquema estrela · Gold DuckDB · SK 0 = membro desconhecido · SCD Tipo 1")
    c.setStrokeColor(colors.HexColor("#d7dfd9"))
    c.line(42, H - 80, W - 42, H - 80)

    bw, bh = 190, 125
    dim_tempo = box(c, 55, H - 245, bw, bh, "dim_tempo", ["SK: sk_tempo", "Grão: uma data", "data_completa, ano, mês", "dia da semana, trimestre", "Role: compra / entrega"], colors.white)
    dim_produto = box(c, 55, 205, bw, bh, "dim_produto", ["SK: sk_produto", "NK: product_id", "categoria_pt / categoria_en", "peso, dimensões, volume", "faixa_peso, flags imputação"], colors.white)
    dim_cliente = box(c, 55, 55, bw, bh, "dim_cliente", ["SK: sk_cliente", "NK: customer_unique_id", "Uma linha por pessoa", "Endereço fica na fato", "Recompra por cliente único"], colors.white)

    dim_vendedor = box(c, W - 245, H - 245, bw, bh, "dim_vendedor", ["SK: sk_vendedor", "NK: seller_id", "cidade, UF, região", "cod_ibge, município", "método do match municipal"], colors.white)
    dim_geo = box(c, W - 245, 205, bw, bh, "dim_geografia", ["SK: sk_geografia", "NK: cod_ibge", "município, UF, região", "população / PIB 2017", "porte e coordenadas"], colors.white)
    dim_pag = box(c, W - 245, 55, bw, bh, "dim_pagamento", ["SK: sk_pagamento", "NK: tipo + parcelas", "tipo predominante", "faixa de parcelas", "pagamento não é faturamento"], colors.white)

    fact_w, fact_h = 300, 218
    fact_item = box(c, W / 2 - fact_w - 16, 175, fact_w, fact_h, "fato_item_pedido", ["Grão: pedido + order_item_id", "FKs: tempo, produto, cliente", "vendedor, geografia, pagamento", "Medidas: valor_produto", "valor_frete, valor_total_item", "dias, atraso, distância", "nota, flag de outlier"], mint, mint)
    fact_order = box(c, W / 2 + 16, 175, fact_w, fact_h, "fato_pedido", ["Grão: um order_id", "FKs: tempo, cliente, geografia", "pagamento; order_id degenerada", "Medidas: valores agregados", "qtd itens / vendedores / produtos", "prazo, atraso, nota", "entregue e avaliação"], mint, mint)

    for dim in (dim_tempo, dim_produto, dim_cliente, dim_vendedor, dim_geo, dim_pag):
        connect(c, dim, fact_item)
        connect(c, dim, fact_order if dim in (dim_tempo, dim_cliente, dim_geo, dim_pag) else fact_item)

    c.setFillColor(muted)
    c.setFont("Helvetica", 9)
    c.drawString(43, 22, "Fonte da camada Gold: data/gold/dw.duckdb | Entradas: contrato Silver → Gold v2")
    c.drawRightString(W - 43, 22, "Projeto acadêmico · Olist + IBGE + SIDRA")
    c.save()
    print(PDF)


if __name__ == "__main__":
    main()
