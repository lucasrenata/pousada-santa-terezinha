from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.units import cm
from datetime import datetime
import os
from sqlalchemy.orm import Session
from database import SessionLocal
import models

class ProfessionalReport:
    """
    Engine de PDF estilo Qualitec: ReportLab para estrutura e design premium.
    """
    def __init__(self, filename, title="Relatório"):
        self.filename = filename
        self.path = os.path.join("reports", filename)
        os.makedirs("reports", exist_ok=True)
        self.title = title
        self.styles = getSampleStyleSheet()
        self.doc = SimpleDocTemplate(self.path, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        self.story = []
        
        # Estilos Customizados
        self.styles.add(ParagraphStyle(
            name='PropertyTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor("#0f172a"), # Navy Dark
            spaceAfter=15,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='PropertyHeader',
            fontSize=9,
            textColor=colors.HexColor("#64748b"), # Slate 500
            alignment=2 # Right
        ))

        self.styles.add(ParagraphStyle(
            name='PropertyKPI',
            fontSize=11,
            textColor=colors.HexColor("#334155"), # Slate 700
            alignment=1, # Center
            fontName='Helvetica-Bold'
        ))

    def _get_pousada_name(self):
        db = SessionLocal()
        try:
            setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == 'pousada_name').first()
            return setting.value if setting else "Estabelecimento"
        finally:
            db.close()

    def add_header(self):
        p_name = self._get_pousada_name()
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        header_text = f"<b>{p_name}</b><br/>Gerado em: {now}"
        self.story.append(Paragraph(header_text, self.styles['PropertyHeader']))
        self.story.append(Spacer(1, 0.3*cm))
        self.story.append(Paragraph(self.title, self.styles['PropertyTitle']))
        self.story.append(Spacer(1, 0.4*cm))

    def add_kpi_cards(self, cards: list):
        """
        Renderiza como cards elegantes com bordas suaves.
        """
        data = [[Paragraph(f"<font color='#64748b' size=9>{c['label']}</font><br/><br/><font size=15><b>{c['value']}</b></font>", self.styles['PropertyKPI']) for c in cards]]
        
        cw = (A4[0] - 4*cm) / len(cards)
        t = Table(data, colWidths=[cw]*len(cards))
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")), 
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")), 
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        self.story.append(t)
        self.story.append(Spacer(1, 0.8*cm))

    def add_table(self, data, col_widths=None, align='CENTER'):
        """Adiciona uma tabela estilizada Premium."""
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0f172a")), # Navy Black
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), align),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.1, colors.HexColor("#f1f5f9")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]) 
        ]))
        self.story.append(t)

    def build(self):
        self.doc.build(self.story)
        return self.path
