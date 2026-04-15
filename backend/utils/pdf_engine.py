from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.units import cm
from datetime import datetime
import os
from sqlalchemy.orm import Session
from database import SessionLocal
import models

class ProfessionalReport:
    """
    Engine de PDF Evoluída: Suporta numeração de páginas, TOC e design bancário.
    """
    def __init__(self, filename, title="Relatório", tenant_id=None):
        self.filename = filename
        self.path = os.path.join("reports", filename)
        os.makedirs("reports", exist_ok=True)
        self.title = title
        self.tenant_id = tenant_id
        self.styles = getSampleStyleSheet()
        self.doc = SimpleDocTemplate(
            self.path, 
            pagesize=A4, 
            rightMargin=1.5*cm, 
            leftMargin=1.5*cm, 
            topMargin=2*cm, 
            bottomMargin=2.5*cm
        )
        self.story = []
        self._p_name = self._get_pousada_name()
        
        # Estilos Customizados de Alta Fidelidade
        self.styles.add(ParagraphStyle(
            name='ExecTitle',
            parent=self.styles['Heading1'],
            fontSize=22,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=20,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='ExecSubtitle',
            fontSize=10,
            textColor=colors.HexColor("#64748b"),
            alignment=0,
            spaceAfter=10
        ))

        self.styles.add(ParagraphStyle(
            name='ExecTOC',
            fontSize=11,
            textColor=colors.HexColor("#334155"),
            leftIndent=10,
            spaceBefore=5,
            bulletText='•'
        ))

    def _get_pousada_name(self):
        db = SessionLocal()
        try:
            if self.tenant_id:
                from database import set_tenant_context
                set_tenant_context(db, self.tenant_id)
            setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == 'pousada_name').first()
            return setting.value if setting else "Estabelecimento"
        finally:
            db.close()

    def add_header(self, subtitle=""):
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.story.append(Paragraph(f"<a name='TOP'/>{self.title}", self.styles['ExecTitle']))
        if subtitle:
            self.story.append(Paragraph(subtitle, self.styles['ExecSubtitle']))
        self.story.append(Spacer(1, 0.5*cm))

    def add_toc(self, items):
        """Adiciona um sumário clicável."""
        self.story.append(Paragraph("Sumário Executivo", self.styles['Heading3']))
        self.story.append(Spacer(1, 0.2*cm))
        for label, anchor in items:
            self.story.append(Paragraph(f"<a href='#{anchor}' color='#2563eb'>{label}</a>", self.styles['ExecTOC']))
        self.story.append(Spacer(1, 1*cm))

    def add_section_header(self, text, anchor=None):
        if anchor:
            text = f"<a name='{anchor}'/>{text}"
        self.story.append(Paragraph(text, self.styles['Heading2']))
        self.story.append(Spacer(1, 0.3*cm))

    def add_kpi_cards(self, cards: list):
        data = [[Paragraph(f"<font color='#64748b' size=8>{c['label']}</font><br/><br/><font size=14><b>{c['value']}</b></font>", self.styles['Normal']) for c in cards]]
        cw = (A4[0] - 3*cm) / len(cards)
        t = Table(data, colWidths=[cw]*len(cards))
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")), 
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")), 
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        self.story.append(t)
        self.story.append(Spacer(1, 0.8*cm))

    def add_table(self, data, col_widths=None, align='CENTER'):
        t = Table(data, colWidths=col_widths, hAlign=align)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")), 
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.1, colors.HexColor("#cbd5e1")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]) 
        ]))
        self.story.append(t)
        self.story.append(Spacer(1, 0.5*cm))

    def _draw_footer(self, canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setStrokeColor(colors.HexColor("#e2e8f0"))
        canvas.line(1.5*cm, 1.5*cm, A4[0]-1.5*cm, 1.5*cm)
        
        # Nome da Pousada e Data
        canvas.drawString(1.5*cm, 1.1*cm, f"{self._p_name} - Relatório Executivo")
        
        # Numeração
        page_num = canvas.getPageNumber()
        canvas.drawRightString(A4[0]-1.5*cm, 1.1*cm, f"Página {page_num}")
        canvas.restoreState()

    def build(self):
        self.doc.build(self.story, onFirstPage=self._draw_footer, onLaterPages=self._draw_footer)
        return self.path
