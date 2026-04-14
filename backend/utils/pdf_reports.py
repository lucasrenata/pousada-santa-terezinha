from utils.pdf_engine import ProfessionalReport
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer
from reportlab.lib import colors

def generate_financial_report(data, filename="relatorio_financeiro.pdf"):
    report = ProfessionalReport(filename, "Demonstrativo Financeiro Executivo")
    report.add_header()
    
    # 1. KPI Cards
    kpis = [
        {"label": "Receita Total", "value": f"RS {data.get('total_revenue', 0):.2f}"},
        {"label": "Transações", "value": str(data.get('transactions', 0))},
        {"label": "Ticket Médio", "value": f"RS {data.get('avg_ticket', 0):.2f}"}
    ]
    report.add_kpi_cards(kpis)

    # 2. Tabelas de Resumo (Duas colunas)
    report.story.append(Paragraph("Resumo de Distribuição", report.styles['Heading3']))
    report.story.append(Spacer(1, 0.4*cm))

    # Vamos criar uma tabela invisível para colocar as duas tabelas de resumo lado a lado ou uma abaixo da outra com melhor espaçamento
    # Por meio de Pagamento
    pay_data = [["Meio de Pagamento", "Total Recebido"]]
    by_method = data.get("by_method", {})
    if not by_method:
        pay_data.append(["N/A", "RS 0.00"])
    for method, val in by_method.items():
        pay_data.append([method.upper(), f"RS {val:.2f}"])
    
    report.add_table(pay_data, col_widths=[7*cm, 5*cm], align='LEFT')
    report.story.append(Spacer(1, 0.6*cm))

    # Por Categoria
    cat_data = [["Categoria", "Valor Total"]]
    by_category = data.get("by_category", {})
    if not by_category:
        cat_data.append(["N/A", "RS 0.00"])
    for cat, val in by_category.items():
        cat_data.append([cat.title(), f"RS {val:.2f}"])
    
    report.add_table(cat_data, col_widths=[7*cm, 5*cm], align='LEFT')
    report.story.append(Spacer(1, 1.2*cm))

    # 3. Histórico Detalhado (O "pulo do gato" para ficar profissional)
    report.story.append(Paragraph("Histórico de Transações Detalhado", report.styles['Heading3']))
    report.story.append(Spacer(1, 0.4*cm))

    hist_data = [["Data", "Descrição", "Categoria", "Método", "Valor"]]
    for tx in data.get("transactions_list", []):
        hist_data.append([
            tx["data"],
            tx["desc"][:30] + "..." if len(tx["desc"]) > 30 else tx["desc"],
            tx["cat"],
            tx["metodo"],
            f"RS {tx['valor']:.2f}"
        ])
    
    if len(hist_data) == 1:
        hist_data.append(["-", "Nenhuma transação registrada", "-", "-", "RS 0.00"])

    report.add_table(hist_data, col_widths=[2.5*cm, 6*cm, 3*cm, 2.5*cm, 3*cm])
    
    return report.build()

def generate_inventory_report(data, filename="relatorio_estoque.pdf"):
    report = ProfessionalReport(filename, "Inventário e Avaliação de Ativos")
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
    report = ProfessionalReport(filename, "Lista de Compras e Reposição Sugerida")
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
