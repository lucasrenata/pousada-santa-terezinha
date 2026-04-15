from utils.pdf_engine import ProfessionalReport
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

def generate_inventory_report(data, filename="relatorio_estoque.pdf", tenant_id=None):
    report = ProfessionalReport(filename, "Inventário e Avaliação de Ativos", tenant_id=tenant_id)
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

def generate_shopping_list_report(data, filename="lista_de_compras.pdf", tenant_id=None):
    report = ProfessionalReport(filename, "Lista de Compras e Reposição Sugerida", tenant_id=tenant_id)
    report.add_header()
    
    # KPIs
    total_to_buy = len(data.get("items", []))
    report.add_kpi_cards([
        {"label": "Produtos na Lista", "value": str(total_to_buy)},
        {"label": "Urgência", "value": "ALTA" if any(i['is_critical'] for i in data.get("items", [])) else "MÉDIA"}
    ])

    # Tabela
    table_data = [["Produto", "Categoria", "Estoque", "Últ. Preço", "Status", "Sugestão"]]
    for i in data.get("items", []):
        table_data.append([
            i['name'],
            i['category'],
            str(i['stock']),
            f"R$ {i.get('cost_price', 0):.2f}",
            "CRÍTICO" if i['is_critical'] else "ALERTA",
            f"+ {i['suggested_buy']} {i.get('unit', 'un')}"
        ])
        
    report.add_table(table_data, col_widths=[5*cm, 3*cm, 2*cm, 2.5*cm, 2.5*cm, 3*cm])
    
    report.story.append(Spacer(1, 1*cm))
    report.story.append(Paragraph("<i>* A sugestão de compra visa atingir o nível de segurança (Mínimo x 2).</i>", report.styles['Italic']))
    
    return report.build()
