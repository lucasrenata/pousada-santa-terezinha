from utils.pdf_engine import PousadaProfessionalReport
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer
from reportlab.lib import colors

def generate_financial_report(data, filename="relatorio_financeiro.pdf"):
    report = PousadaProfessionalReport(filename, "Relatório Financeiro")
    report.add_header()
    
    # Detalhes do Período
    report.story.append(Paragraph(f"<b>Período:</b> {data.get('period', 'N/A')}", report.styles['Normal']))
    report.story.append(Spacer(1, 0.3*cm))
    
    # Resumo em tabela de 2 colunas
    summary_data = [
        ["Total de Receita", f"R$ {data.get('total_revenue', 0):.2f}"],
        ["Total de Transações", str(data.get('transactions', 0))]
    ]
    report.add_table(summary_data, col_widths=[5*cm, 5*cm])
    report.story.append(Spacer(1, 1*cm))
    
    # Categorias
    report.story.append(Paragraph("Detalhamento por Categoria", report.styles['Heading3']))
    report.story.append(Spacer(1, 0.3*cm))
    
    cat_data = [["Categoria", "Valor Total"]]
    for cat, val in data.get("by_category", {}).items():
        cat_data.append([cat, f"R$ {val:.2f}"])
        
    report.add_table(cat_data, col_widths=[8*cm, 4*cm])
    
    return report.build()

def generate_inventory_report(data, filename="relatorio_estoque.pdf"):
    report = PousadaProfessionalReport(filename, "Relatório de Estoque e Compras")
    report.add_header()
    
    # Tabela de Produtos
    table_data = [["Produto", "Estoque", "Mínimo", "Status"]]
    shopping_list = []
    
    for p in data.get("products", []):
        name = p.get("name", "N/A")
        stock = p.get("stock", 0)
        min_s = p.get("min_stock", 0)
        
        status = "OK"
        if stock < min_s:
            status = "REPOR"
            shopping_list.append(name)
            
        table_data.append([name, str(stock), str(min_s), status])
        
    report.add_table(table_data, col_widths=[8*cm, 2.5*cm, 2.5*cm, 3.5*cm])
    report.story.append(Spacer(1, 1*cm))
    
    if shopping_list:
        report.story.append(Paragraph("LISTA DE COMPRAS SUGERIDA", report.styles['Heading3']))
        report.story.append(Spacer(1, 0.3*cm))
        for item in shopping_list:
            report.story.append(Paragraph(f"• {item}", report.styles['Normal']))
            
    return report.build()
