from utils.pdf_engine import PousadaProfessionalReport
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer
from reportlab.lib import colors

def generate_financial_report(data, filename="relatorio_financeiro.pdf"):
    report = PousadaProfessionalReport(filename, "Demonstrativo Financeiro Executivo")
    report.add_header()
    
    # 1. KPI Cards
    kpis = [
        {"label": "Receita Total", "value": f"R$ {data.get('total_revenue', 0):.2f}"},
        {"label": "Transações", "value": str(data.get('transactions', 0))},
        {"label": "Ticket Médio", "value": f"R$ {data.get('avg_ticket', 0):.2f}"}
    ]
    report.add_kpi_cards(kpis)

    # 2. Distribuição por Meio de Pagamento
    report.story.append(Paragraph("Distribuição de Recebimentos", report.styles['Heading3']))
    report.story.append(Spacer(1, 0.3*cm))
    
    pay_data = [["Meio de Pagamento", "Total Recebido"]]
    for method, val in data.get("by_method", {}).items():
        pay_data.append([method.upper(), f"R$ {val:.2f}"])
    report.add_table(pay_data, col_widths=[8*cm, 5*cm], align='LEFT')
    report.story.append(Spacer(1, 0.8*cm))

    # 3. Categorias
    report.story.append(Paragraph("Mix de Receita por Categoria", report.styles['Heading3']))
    report.story.append(Spacer(1, 0.3*cm))
    
    cat_data = [["Categoria", "Valor Total"]]
    for cat, val in data.get("by_category", {}).items():
        cat_data.append([cat.title(), f"R$ {val:.2f}"])
    report.add_table(cat_data, col_widths=[8*cm, 5*cm], align='LEFT')
    
    return report.build()

def generate_inventory_report(data, filename="relatorio_estoque.pdf"):
    report = PousadaProfessionalReport(filename, "Inventário e Avaliação de Ativos")
    report.add_header()
    
    # 1. KPIs de Estoque
    total_items = len(data.get("products", []))
    critical_count = sum(1 for p in data.get("products", []) if p.get("stock", 0) <= p.get("min_stock", 0))
    total_value = data.get("total_inventory_value", 0)

    kpis = [
        {"label": "Total de Itens", "value": str(total_items)},
        {"label": "Itens em Alerta", "value": str(critical_count)},
        {"label": "Valor em Estoque", "value": f"R$ {total_value:.2f}"}
    ]
    report.add_kpi_cards(kpis)

    # 2. Tabela Detalhada
    table_data = [["ID", "Produto", "Categoria", "Estoque", "Mínimo", "Valor Unit.", "Subtotal"]]
    for p in data.get("products", []):
        stock = p.get("stock", 0)
        min_s = p.get("min_stock", 0)
        price = p.get("price", 0)
        subtotal = stock * price
        
        table_data.append([
            str(p.get("id", "")),
            p.get("name", "N/A"),
            p.get("category", "Geral"),
            str(stock),
            str(min_s),
            f"R$ {price:.2f}",
            f"R$ {subtotal:.2f}"
        ])
        
    report.add_table(table_data, col_widths=[1*cm, 5*cm, 3*cm, 2*cm, 2*cm, 2*cm, 2.5*cm])
    
    return report.build()

def generate_shopping_list_report(data, filename="lista_de_compras.pdf"):
    report = PousadaProfessionalReport(filename, "Lista de Compras e Reposição Sugerida")
    report.add_header()
    
    # KPIs
    total_to_buy = len(data.get("items", []))
    report.add_kpi_cards([
        {"label": "Produtos na Lista", "value": str(total_to_buy)},
        {"label": "Urgência", "value": "ALTA" if any(i['is_critical'] for i in data.get("items", [])) else "MÉDIA"}
    ])

    # Tabela
    table_data = [["Produto", "Categoria", "Estoque", "Mínimo", "Status", "Sugestão"]]
    for i in data.get("items", []):
        row_color = colors.red if i['is_critical'] else colors.orange
        table_data.append([
            i['name'],
            i['category'],
            str(i['stock']),
            str(i['min_stock']),
            "CRÍTICO" if i['is_critical'] else "ALERTA",
            f"+ {i['suggested_buy']} {i.get('unit', 'un')}"
        ])
        
    report.add_table(table_data, col_widths=[5.5*cm, 3.5*cm, 2*cm, 2*cm, 2.5*cm, 2.5*cm])
    
    report.story.append(Spacer(1, 1*cm))
    report.story.append(Paragraph("<i>* A sugestão de compra visa atingir o nível de segurança (Mínimo x 2).</i>", report.styles['Italic']))
    
    return report.build()
