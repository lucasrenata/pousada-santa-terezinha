from utils.pdf_engine import ProfessionalReport
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, PageBreak

def generate_financial_report(data, filename="relatorio_financeiro.pdf", tenant_id=None, mode="full"):
    """
    Gera um relatório financeiro de alto nível.
    mode: 'full' (completo com extrato) ou 'summary' (apenas visão geral)
    """
    tenant_name = data.get('tenant_name', 'Pousada')
    title = f"{tenant_name.upper()}<br/>Relatório Financeiro" if mode == "full" else f"{tenant_name.upper()}<br/>Demonstrativo Financeiro Resumido"
    report = ProfessionalReport(filename, title, tenant_id=tenant_id)
    
    # 1. Cabeçalho e Sumário
    periodo = f"{data.get('start', '')} até {data.get('end', '')}"
    
    subtitle = f"Período: {periodo}"
    if data.get('tenant_cnpj'):
        subtitle += f" | CNPJ: {data['tenant_cnpj']}"
    if data.get('tenant_address'):
        subtitle += f"\nEndereço: {data['tenant_address']}"
        
    report.add_header(subtitle=subtitle)
    
    toc_items = [("Visão Geral do Período", "OVERVIEW")]
    if mode == "full":
        toc_items.extend([
            ("Detalhamento de Entradas (Receitas)", "INCOMES"),
            ("Detalhamento de Saídas (Despesas)", "OUTCOMES"),
            ("Evolução do Fluxo de Caixa Diário", "FLOW")
        ])
    report.add_toc(toc_items)

    # 2. Seção: Visão Geral
    report.add_section_header("Visão Geral do Período", anchor="OVERVIEW")
    
    # KPIs Principais
    total_rev = data.get('total_revenue', 0)
    total_exp = data.get('total_expense', 0)
    total_disc = data.get('total_discounts', 0)
    net = total_rev - total_exp
    
    kpis = [
        {"label": "Receita Bruta", "value": f"R$ {total_rev:.2f}"},
        {"label": "Despesas Pagas", "value": f"R$ {total_exp:.2f}"},
        {"label": "Total Descontos", "value": f"R$ {total_disc:.2f}"},
        {"label": "Saldo Líquido", "value": f"R$ {net:.2f}"}
    ]
    report.add_kpi_cards(kpis)
    
    # Mini Tabelas de Distribuição
    all_cats = set(list(data.get("by_category", {}).keys()) + list(data.get("expense_by_category", {}).keys()))
    cat_data = [["Categoria", "Receita", "Despesa"]]
    for cat in sorted(all_cats):
        rv = data.get("by_category", {}).get(cat, 0)
        ex = data.get("expense_by_category", {}).get(cat, 0)
        cat_data.append([cat.title(), f"R$ {rv:.2f}", f"R$ {ex:.2f}"])
    
    report.add_table(cat_data, col_widths=[6*cm, 4*cm, 4*cm], title="Distribuição por Categoria")
    
    # Nova mini-tabela: Meios de Pagamento (Receitas)
    pay_data = [["Meio de Pagamento", "Total Recebido"]]
    for m, val in data.get("pay_summary", {}).items():
        pay_data.append([m.upper(), f"R$ {val:.2f}"])
    if len(pay_data) == 1: pay_data.append(["-", "Nenhuma entrada"])
    report.add_table(pay_data, col_widths=[7*cm, 7*cm], title="Resumo por Meio de Pagamento (Entradas)")
    
    report.story.append(Spacer(1, 1*cm))

    if mode == "full":
        # 3. Seção: Entradas
        report.story.append(PageBreak())
        report.add_section_header("Detalhamento de Entradas (Receitas)", anchor="INCOMES")
        hist_in = [["Data", "Descrição", "Categoria", "Método", "Valor"]]
        for tx in data.get("incomes_list", []):
            hist_in.append([
                tx["data"],
                tx["desc"][:28] + ".." if len(tx["desc"]) > 28 else tx["desc"],
                tx["cat"],
                tx.get("metodo", "-"),
                f"R$ {tx['valor']:.2f}"
            ])
        if len(hist_in) == 1: hist_in.append(["-", "Nenhuma entrada", "-", "-", "-"])
        report.add_table(hist_in, col_widths=[2.5*cm, 6.5*cm, 2.5*cm, 2.5*cm, 3.5*cm])

        # 4. Seção: Saídas
        report.story.append(Spacer(1, 1*cm))
        report.add_section_header("Detalhamento de Saídas (Despesas)", anchor="OUTCOMES")
        hist_out = [["Data", "Descrição", "Categoria", "Método", "Valor"]]
        for tx in data.get("outcomes_list", []):
            hist_out.append([
                tx["data"],
                tx["desc"][:25] + ".." if len(tx["desc"]) > 25 else tx["desc"],
                tx["cat"],
                tx["metodo"],
                f"R$ {tx['valor']:.2f}"
            ])
        if len(hist_out) == 1: hist_out.append(["-", "Nenhuma saída", "-", "-", "-"])
        report.add_table(hist_out, col_widths=[2.5*cm, 6*cm, 3*cm, 2.5*cm, 3.2*cm])

        # 5. Seção: Fluxo Diário
        report.story.append(PageBreak())
        report.add_section_header("Evolução do Fluxo de Caixa Diário", anchor="FLOW")
        flow_data = [["Data", "Entradas", "Saídas", "Saldo do Dia"]]
        for d in data.get("timeline", []):
            flow_data.append([
                d["date"], f"R$ {d['revenue']:.2f}", f"R$ {d['expense']:.2f}", 
                Paragraph(f"<font color='{'#16a34a' if d['net']>=0 else '#dc2626'}'>R$ {d['net']:.2f}</font>", report.styles['Normal'])
            ])
        report.add_table(flow_data, col_widths=[4*cm, 4*cm, 4*cm, 4*cm])

    return report.build()
