from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.units import cm
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend
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
        self._info = self._get_pousada_info()
        
        # Estilos Customizados de Alta Fidelidade (Padrão Moderno)
        self.styles.add(ParagraphStyle(
            name='ExecTitle',
            fontSize=24,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=2,
            fontName='Helvetica-Bold',
            leading=28
        ))
        
        self.styles.add(ParagraphStyle(
            name='ExecSubtitle',
            fontSize=10,
            textColor=colors.HexColor("#64748b"),
            alignment=0,
            spaceAfter=12,
            fontName='Helvetica',
            leading=12
        ))

        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            fontSize=16,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=15,
            spaceAfter=10,
            fontName='Helvetica-Bold',
            borderPadding=(0, 0, 5, 0),
            leading=20
        ))

        self.styles.add(ParagraphStyle(
            name='TableTitle',
            fontSize=11,
            textColor=colors.HexColor("#334155"),
            spaceBefore=12,
            spaceAfter=6,
            fontName='Helvetica-BoldOblique',
            leading=14
        ))

        self.styles.add(ParagraphStyle(
            name='ExecTOC',
            fontSize=11,
            textColor=colors.HexColor("#2563eb"),
            leftIndent=10,
            spaceBefore=5,
            bulletText='•',
            fontName='Helvetica'
        ))

    def _get_pousada_info(self):
        db = SessionLocal()
        try:
            if self.tenant_id:
                from database import set_tenant_context
                set_tenant_context(db, self.tenant_id)
            
            # Buscar todos os dados relevantes
            keys = ['pousada_name', 'pousada_cnpj', 'pousada_address']
            settings = db.query(models.SystemSetting).filter(models.SystemSetting.key.in_(keys)).all()
            info = {s.key: s.value for s in settings}
            
            return {
                "name": info.get('pousada_name', 'Estabelecimento'),
                "cnpj": info.get('pousada_cnpj', ''),
                "address": info.get('pousada_address', '')
            }
        finally:
            db.close()

    def add_header(self, subtitle=""):
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        # Nome do Estabelecimento (Grande)
        self.story.append(Paragraph(self._info['name'].upper(), self.styles['ExecTitle']))
        
        # Dados do Estabelecimento (CNPJ / Endereço) - Pequeno e elegante
        meta_text = ""
        if self._info['cnpj']: meta_text += f"CNPJ: {self._info['cnpj']} "
        if self._info['address']: meta_text += f"| {self._info['address']}"
        
        if meta_text:
            self.story.append(Paragraph(meta_text, self.styles['ExecSubtitle']))
        
        self.story.append(Spacer(1, 0.4*cm))
        
        # Título do Relatório e Data
        header_table_data = [[
            Paragraph(f"<b>{self.title}</b>", self.styles['Normal']),
            Paragraph(f"<font color='#64748b' size=8>Gerado em: {now}</font>", self.styles['Normal'])
        ]]
        t = Table(header_table_data, colWidths=[12*cm, 5.5*cm])
        t.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))
        self.story.append(t)
        
        if subtitle:
            self.story.append(Spacer(1, 0.3*cm))
            self.story.append(Paragraph(subtitle, self.styles['ExecSubtitle']))
            
        self.story.append(Spacer(1, 0.8*cm))

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
        self.story.append(Paragraph(text, self.styles['SectionTitle']))
        # Linha decorativa sob o título da seção
        line_data = [[""]]
        line_table = Table(line_data, colWidths=[A4[0] - 3*cm])
        line_table.setStyle(TableStyle([
            ('LINEBELOW', (0,0), (-1,-1), 1, colors.HexColor("#e2e8f0"))
        ]))
        self.story.append(line_table)
        self.story.append(Spacer(1, 0.4*cm))

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

    def add_table(self, data, col_widths=None, align='CENTER', title=None):
        if title:
            self.story.append(Paragraph(title, self.styles['TableTitle']))
            
        t = Table(data, colWidths=col_widths, hAlign=align)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0f172a")), # Darker navy
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10), # Slightly larger header
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.1, colors.HexColor("#e2e8f0")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 1), (-1, -1), 9), # Slightly larger body
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]) 
        ]))
        self.story.append(t)
        self.story.append(Spacer(1, 0.8*cm))

    def add_paragraph(self, text, style_name='Normal'):
        """Adiciona um bloco de texto (análise do robô)."""
        if style_name not in self.styles:
            style_name = 'Normal'
        self.story.append(Paragraph(text, self.styles[style_name]))
        self.story.append(Spacer(1, 0.4*cm))

    def add_pie_chart(self, data, labels, title=""):
        """Adiciona um gráfico de pizza profissional."""
        if not data: return
        
        if title:
            self.story.append(Paragraph(title, self.styles['Heading3']))
            self.story.append(Spacer(1, 0.2*cm))

        drawing = Drawing(width=400, height=200)
        pc = Pie()
        pc.x = 150
        pc.y = 25
        pc.width = 150
        pc.height = 150
        pc.data = data
        pc.labels = labels
        
        pc.sideLabels = True
        pc.slices.strokeWidth = 0.5
        
        # Cores elegantes
        col_palette = [
            colors.HexColor("#2563eb"), colors.HexColor("#16a34a"), 
            colors.HexColor("#dc2626"), colors.HexColor("#eab308"), 
            colors.HexColor("#9333ea"), colors.HexColor("#0891b2")
        ]
        for i, color in enumerate(col_palette):
            if i < len(pc.slices):
                pc.slices[i].fillColor = color

        drawing.add(pc)
        
        # Adiciona legenda lateral
        legend = Legend()
        legend.x = 20
        legend.y = 100
        legend.dx = 8
        legend.dy = 8
        legend.fontName = 'Helvetica'
        legend.fontSize = 8
        legend.columnMaximum = 10
        legend.colorNamePairs = list(zip(col_palette, labels))
        drawing.add(legend)

        self.story.append(drawing)
        self.story.append(Spacer(1, 0.8*cm))

    def _draw_footer(self, canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setStrokeColor(colors.HexColor("#e2e8f0"))
        canvas.line(1.5*cm, 1.5*cm, A4[0]-1.5*cm, 1.5*cm)
        
        # Nome da Pousada e Data
        canvas.drawString(1.5*cm, 1.1*cm, f"{self._info['name']} - Relatório Executivo")
        
        # Numeração
        page_num = canvas.getPageNumber()
        canvas.drawRightString(A4[0]-1.5*cm, 1.1*cm, f"Página {page_num}")
        canvas.restoreState()

    def build(self):
        self.doc.build(self.story, onFirstPage=self._draw_footer, onLaterPages=self._draw_footer)
        return self.path
