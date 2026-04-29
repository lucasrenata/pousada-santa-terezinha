from utils.pdf_engine import ProfessionalReport
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak

def generate_custom_ai_report(tenant_id: int, filename: str, title: str, sections: list):
    """
    Motor flexível que constrói um relatório baseado em uma lista de seções
    definidas pela inteligência artificial.
    """
    report = ProfessionalReport(filename, title, tenant_id=tenant_id)
    report.add_header(subtitle="Relatório Analítico Gerado por Inteligência Artificial")
    
    toc_items = []
    for i, section in enumerate(sections):
        if section.get("title"):
            anchor = f"SEC_{i}"
            toc_items.append((section["title"], anchor))
            section["anchor"] = anchor
            
    if toc_items:
        report.add_toc(toc_items)

    for section in sections:
        if section.get("type") == "page_break":
            report.story.append(PageBreak())
            continue

        if section.get("title"):
            report.add_section_header(section["title"], anchor=section.get("anchor"))
            
        # Processamento de Componentes da Seção
        components = section.get("components", [])
        for comp in components:
            ctype = comp.get("type")
            
            if ctype == "kpis":
                report.add_kpi_cards(comp.get("cards", []))
                
            elif ctype == "table":
                report.add_table(
                    comp.get("data", []), 
                    col_widths=[float(w)*cm for w in comp.get("col_widths", [])] if comp.get("col_widths") else None
                )
                
            elif ctype == "analysis" or ctype == "text":
                report.add_paragraph(comp.get("content", ""), style_name=comp.get("style", "Normal"))
                
            elif ctype == "pie_chart":
                report.add_pie_chart(
                    comp.get("data", []), 
                    comp.get("labels", []), 
                    title=comp.get("chart_title", "")
                )
                
    return report.build()
