from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from .auth import get_current_staff, get_current_admin

from sqlalchemy.orm import Session
from typing import List, Optional
import models, schemas
from database import get_db
import io, csv
from datetime import datetime, date
import re

router = APIRouter(prefix="/products", tags=["Products/Stock"])

# 1. CRIAR PRODUTO (Com validação de Barcode)
@router.post("/", response_model=schemas.ProductResponse)
def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db), user = Depends(get_current_staff)):
    if product.barcode:
        existing = db.query(models.Product).filter(models.Product.barcode == product.barcode).first()
        if existing:
            raise HTTPException(status_code=400, detail="Código de barras já cadastrado")
            
    new_prod = models.Product(**product.model_dump())
    db.add(new_prod)
    db.commit()
    db.refresh(new_prod)
    return new_prod

# 2. LISTAR (Com filtros)
@router.get("/", response_model=List[schemas.ProductResponse])
def list_products(
    category: Optional[str] = None, 
    only_active: bool = True, 
    db: Session = Depends(get_db),
    user = Depends(get_current_staff)
):
    query = db.query(models.Product)
    
    if only_active:
        query = query.filter(models.Product.is_active == True)
    
    if category:
        query = query.filter(models.Product.category == category)
        
    return query.all()

# 3. DASHBOARD DE ESTOQUE (KPIs da Documentação)
@router.get("/dashboard", response_model=schemas.StockDashboard)
def get_stock_dashboard(db: Session = Depends(get_db), user = Depends(get_current_staff)):
    products = db.query(models.Product).filter(models.Product.is_active == True).all()
    
    total_items = len(products)
    total_value = sum([p.price * p.stock_quantity for p in products])
    
    # Alerta de Estoque Baixo (Estoque Atual <= Mínimo)
    low_stock_list = [p for p in products if p.stock_quantity <= p.min_stock]
    
    return {
        "total_products": total_items,
        "total_value": total_value,
        "low_stock_count": len(low_stock_list),
        "low_stock_items": low_stock_list
    }

# 4. CONSUMO (Mantido, mas checando is_active)
@router.post("/consumption")
def add_consumption(data: schemas.ConsumptionRequest, db: Session = Depends(get_db), user = Depends(get_current_staff)):
    booking = db.query(models.Booking).filter(models.Booking.room_id == data.room_id, models.Booking.status == models.BookingStatus.ATIVO).first()
    if not booking: raise HTTPException(status_code=400, detail="Sem check-in ativo")
    
    product = db.query(models.Product).filter(models.Product.id == data.product_id).first()
    if not product or not product.is_active: 
        raise HTTPException(status_code=404, detail="Produto não encontrado ou inativo")
    
    if product.stock_quantity < data.quantity:
        raise HTTPException(status_code=400, detail=f"Estoque insuficiente. Restam {product.stock_quantity}")
    
    cons = models.Consumption(booking_id=booking.id, product_id=product.id, quantity=data.quantity, unit_price=product.price)
    product.stock_quantity -= data.quantity
    db.add(cons)
    db.commit()
    return {"message": "Consumo registrado", "novo_estoque": product.stock_quantity}

# 5. ATUALIZAR PRODUTO (inclui quantidade e preço)
@router.put("/{product_id}", response_model=schemas.ProductResponse)
def update_product(product_id: int, payload: schemas.ProductUpdate, db: Session = Depends(get_db), user = Depends(get_current_staff)):
    prod = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    if payload.barcode is not None and payload.barcode != prod.barcode:
        exists = db.query(models.Product).filter(models.Product.barcode == payload.barcode).first()
        if exists:
            raise HTTPException(status_code=400, detail="Código de barras já cadastrado")
    if payload.name is not None: prod.name = payload.name
    if payload.price is not None: prod.price = payload.price
    if payload.category is not None: prod.category = payload.category
    if payload.barcode is not None: prod.barcode = payload.barcode
    if payload.unit_measure is not None: prod.unit_measure = payload.unit_measure
    if payload.stock_quantity is not None: prod.stock_quantity = payload.stock_quantity
    if payload.min_stock is not None: prod.min_stock = payload.min_stock
    if payload.max_stock is not None: prod.max_stock = payload.max_stock
    if payload.supplier is not None: prod.supplier = payload.supplier
    if payload.description is not None: prod.description = payload.description
    if payload.is_active is not None: prod.is_active = payload.is_active
    if payload.is_quick_access is not None: prod.is_quick_access = payload.is_quick_access
    if payload.cost_price is not None: prod.cost_price = payload.cost_price
    if payload.markup_percent is not None: prod.markup_percent = payload.markup_percent
    db.commit()
    db.refresh(prod)
    return prod

# 6. RECEBIMENTO DE ESTOQUE VIA NOTA FISCAL (CSV/XLSX) + Registro de histórico
@router.post("/stock/receipt", response_model=schemas.StockEntryResponse)
def stock_receipt(
    file: UploadFile = File(...),
    supplier: Optional[str] = None,
    invoice_number: Optional[str] = None,
    invoice_date: Optional[str] = None,
    note: Optional[str] = None,
    db: Session = Depends(get_db),
    user = Depends(get_current_staff)
):
    filename = file.filename.lower()
    rows: List[dict] = []
    if filename.endswith(".csv"):
        content = file.file.read().decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
    elif filename.endswith(".xlsx"):
        try:
            import openpyxl  # opcional; se não instalado, instruir a instalar
        except ImportError:
            raise HTTPException(status_code=400, detail="Suporte a XLSX requer 'openpyxl'. Instale e tente novamente.")
        wb = openpyxl.load_workbook(file.file, data_only=True)
        ws = wb.active
        headers = []
        for j, cell in enumerate(ws[1], start=1):
            headers.append(str(cell.value).strip().lower() if cell.value else f"col{j}")
        for i, row in enumerate(ws.iter_rows(min_row=2), start=2):
            d = {}
            for j, cell in enumerate(row):
                key = headers[j] if j < len(headers) else f"col{j+1}"
                d[key] = cell.value if cell.value is not None else ""
            rows.append(d)
    elif filename.endswith(".xml"):
        import xml.etree.ElementTree as ET
        content = file.file.read()
        try:
            root = ET.fromstring(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Erro ao processar XML: {str(e)}")

        # O XML de NFe costuma ter namespaces. Vamos tentar buscar de forma flexível.
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
        
        # Se não informou metadados, tentamos extrair do XML
        if not supplier:
            emit = root.find(".//nfe:emit/nfe:xNome", ns)
            if emit is not None: supplier = emit.text
        if not invoice_number:
            nNF = root.find(".//nfe:ide/nfe:nNF", ns)
            if nNF is not None: invoice_number = nNF.text
        if not invoice_date:
            dhEmi = root.find(".//nfe:ide/nfe:dhEmi", ns)
            if dhEmi is not None: 
                invoice_date = dhEmi.text[:10]
            else:
                # Versão 1.10 usa dEmi
                dEmi = root.find(".//nfe:ide/nfe:dEmi", ns)
                if dEmi is not None: invoice_date = dEmi.text[:10]

        # Busca itens
        for det in root.findall(".//nfe:det", ns):
            prod_tag = det.find("nfe:prod", ns)
            if prod_tag is not None:
                barcode = prod_tag.find("nfe:cEAN", ns)
                name = prod_tag.find("nfe:xProd", ns)
                qty = prod_tag.find("nfe:qCom", ns)
                price = prod_tag.find("nfe:vUnCom", ns)
                
                rows.append({
                    "barcode": barcode.text if barcode is not None and barcode.text != "SEM GTIN" else "",
                    "name": name.text if name is not None else "",
                    "quantity": qty.text if qty is not None else "0",
                    "unit_price": price.text if price is not None else ""
                })
    else:
        raise HTTPException(status_code=400, detail="Formato inválido. Envie CSV, XLSX ou XML.")
    
    updated = 0
    processed = 0
    errors = []
    entry = models.StockEntry(
        supplier=supplier,
        invoice_number=invoice_number,
        invoice_date=datetime.strptime(invoice_date, "%Y-%m-%d").date() if invoice_date else None,
        note=note,
        created_at=datetime.now()
    )
    db.add(entry)
    db.flush()  # obtém entry.id
    for idx, row in enumerate(rows, start=2):
        processed += 1
        try:
            barcode = str(row.get("barcode") or "").strip()
            name = str(row.get("name") or "").strip()
            qty_str = str(row.get("quantity") or "0").strip()
            price_str = str(row.get("unit_price") or "").strip()
            # Converte string (que pode ser decimal) para float e depois int
            try:
                quantity = int(float(qty_str)) if qty_str else 0
            except:
                quantity = 0
            if quantity <= 0:
                continue
            prod = None
            if barcode:
                prod = db.query(models.Product).filter(models.Product.barcode == barcode).first()
            if not prod and name:
                prod = db.query(models.Product).filter(models.Product.name.ilike(name)).first()
            if not prod:
                # Se não encontrou, CRIA o produto automaticamente
                unit_price = None
                if price_str:
                    try: unit_price = float(price_str)
                    except: unit_price = 0
                
                # Preço de venda = Compra + 20%
                sale_price = (unit_price * 1.2) if unit_price else 0
                
                prod = models.Product(
                    name=name or "Novo Produto (NF)",
                    barcode=barcode or None,
                    price=sale_price,
                    category="Importado via NF",
                    stock_quantity=0, # Será somado abaixo
                    min_stock=5
                )
                db.add(prod)
                db.flush() # Obtém ID
            
            prod.stock_quantity = (prod.stock_quantity or 0) + quantity
            unit_price = None
            if price_str:
                try:
                    unit_price = float(price_str)
                    prod.price = unit_price
                except:
                    unit_price = None
            item = models.StockEntryItem(entry_id=entry.id, product_id=prod.id, quantity=quantity, unit_price=unit_price)
            db.add(item)
            updated += 1
        except Exception as e:
            errors.append({"line": idx, "error": str(e)})
    db.commit()
    db.refresh(entry)
    # carrega items
    entry.items = db.query(models.StockEntryItem).filter(models.StockEntryItem.entry_id == entry.id).all()
    # anexa erros no response via header? aqui não cabe no pydantic; retornamos somente a entrada
    return entry

# 7. LISTAR HISTÓRICO DE ENTRADAS
@router.get("/stock/entries", response_model=List[schemas.StockEntryResponse])
def list_stock_entries(
    start: Optional[date] = None,
    end: Optional[date] = None,
    supplier: Optional[str] = None,
    invoice_number: Optional[str] = None,
    db: Session = Depends(get_db),
    user = Depends(get_current_staff)
):
    q = db.query(models.StockEntry)
    if start: q = q.filter(models.StockEntry.invoice_date >= start)
    if end: q = q.filter(models.StockEntry.invoice_date <= end)
    if supplier: q = q.filter(models.StockEntry.supplier.ilike(f"%{supplier}%"))
    if invoice_number: q = q.filter(models.StockEntry.invoice_number.ilike(f"%{invoice_number}%"))
    q = q.order_by(models.StockEntry.created_at.desc())
    entries = q.all()
    # eager load items
    for e in entries:
        e.items = db.query(models.StockEntryItem).filter(models.StockEntryItem.entry_id == e.id).all()
    return entries

# 8. RECEBIMENTO DE ESTOQUE VIA OCR (Imagem/PDF)
@router.post("/stock/ocr", response_model=schemas.StockEntryResponse)
def stock_ocr(
    file: UploadFile = File(...),
    supplier: Optional[str] = None,
    invoice_number: Optional[str] = None,
    invoice_date: Optional[str] = None,
    note: Optional[str] = None,
    db: Session = Depends(get_db),
    user = Depends(get_current_staff)
):
    filename = (file.filename or "").lower()
    if not (filename.endswith(".png") or filename.endswith(".jpg") or filename.endswith(".jpeg") or filename.endswith(".pdf")):
        raise HTTPException(status_code=400, detail="Envie imagem PNG/JPG ou PDF")
    try:
        import pytesseract
    except ImportError:
        raise HTTPException(status_code=400, detail="OCR requer 'pytesseract' instalado.")
    text = ""
    if filename.endswith(".pdf"):
        try:
            import fitz
        except ImportError:
            raise HTTPException(status_code=400, detail="Para PDF, instale 'PyMuPDF' (fitz).")
        data = file.file.read()
        doc = fitz.open(stream=data, filetype="pdf")
        if doc.page_count == 0:
            raise HTTPException(status_code=400, detail="PDF vazio")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        try:
            from PIL import Image
        except ImportError:
            raise HTTPException(status_code=400, detail="OCR requer 'Pillow' instalado.")
        import io as iob
        image = Image.open(iob.BytesIO(img_bytes))
        text = pytesseract.image_to_string(image, lang="por")
    else:
        try:
            from PIL import Image
        except ImportError:
            raise HTTPException(status_code=400, detail="OCR requer 'Pillow' instalado.")
        image = Image.open(file.file)
        text = pytesseract.image_to_string(image, lang="por")
    lines = [re.sub(r"\s+", " ", l.strip()) for l in text.splitlines() if l.strip()]
    items: List[dict] = []
    price_regex = re.compile(r"(?:R\\$\\s*)?(\\d{1,3}(?:\\.\\d{3})*,\\d{2}|\\d+\\.\\d{2})")
    qty_label = re.compile(r"qtd\\s*[:\\-]?\\s*(\\d+)", re.IGNORECASE)
    unit_words = ["UN", "UND", "UNID", "KG", "L", "CX", "PC"]
    for line in lines:
        if any(k in line.upper() for k in ["TOTAL", "SUBTOTAL", "VALOR TOTAL"]):
            continue
        qty = None
        m = qty_label.search(line)
        if m:
            try:
                qty = int(m.group(1))
            except:
                qty = None
        if qty is None:
            parts = re.findall(r"(\\d+)", line)
            if parts:
                try:
                    qty = int(parts[0])
                except:
                    qty = None
        price = None
        mp = price_regex.search(line.replace(" ", ""))
        if mp:
            val = mp.group(1)
            val = val.replace(".", "").replace(",", ".")
            try:
                price = float(val)
            except:
                price = None
        name = line
        for w in unit_words:
            name = re.sub(rf"\\b{w}\\b", "", name, flags=re.IGNORECASE)
        name = re.sub(r"qtd\\s*[:\\-]?\\s*\\d+", "", name, flags=re.IGNORECASE)
        name = re.sub(r"(?:R\\$)?\\s*\\d+[.,]\\d{2}", "", name)
        name = re.sub(r"\\b\\d+\\b", "", name)
        name = re.sub(r"\\s+", " ", name).strip()
        if qty and name and len(name) > 2:
            items.append({"name": name, "quantity": qty, "unit_price": price})
    entry = models.StockEntry(
        supplier=supplier,
        invoice_number=invoice_number,
        invoice_date=datetime.strptime(invoice_date, "%Y-%m-%d").date() if invoice_date else None,
        note=note,
        created_at=datetime.now()
    )
    db.add(entry)
    db.flush()
    for it in items:
        found = None
        digits = re.findall(r"\\d{8,13}", it["name"])
        if digits:
            bcode = digits[0]
            found = db.query(models.Product).filter(models.Product.barcode == bcode).first()
        if not found:
            tokens = [t for t in re.split(r"\\W+", it["name"]) if len(t) >= 3]
            if tokens:
                q = db.query(models.Product)
                score = {}
                for t in tokens:
                    for p in q.filter(models.Product.name.ilike(f"%{t}%")).all():
                        score[p.id] = score.get(p.id, 0) + 1
                if score:
                    best_id = max(score, key=score.get)
                    found = db.query(models.Product).filter(models.Product.id == best_id).first()
        if not found:
            # Se não encontrou via OCR, cria o novo produto
            p_unit = it.get("unit_price") or 0
            sale_p = p_unit * 1.2
            found = models.Product(
                name=it["name"] or "Novo Produto (OCR)",
                price=sale_p,
                category="Importado via OCR",
                stock_quantity=0,
                min_stock=5
            )
            db.add(found)
            db.flush()
        
        found.stock_quantity = (found.stock_quantity or 0) + int(it["quantity"])
        unit_price = it.get("unit_price")
        if unit_price:
            found.price = unit_price
        item = models.StockEntryItem(entry_id=entry.id, product_id=found.id, quantity=int(it["quantity"]), unit_price=unit_price)
        db.add(item)
    db.commit()
    db.refresh(entry)
    entry.items = db.query(models.StockEntryItem).filter(models.StockEntryItem.entry_id == entry.id).all()
    return entry

@router.delete("/stock/entries/{entry_id}")
def delete_stock_entry(entry_id: int, db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    """Exclui uma entrada de estoque e reverte as quantidades dos produtos."""
    entry = db.query(models.StockEntry).filter(models.StockEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entrada não encontrada")
    
    # Busca itens para reverter o estoque
    items = db.query(models.StockEntryItem).filter(models.StockEntryItem.entry_id == entry_id).all()
    for it in items:
        prod = db.query(models.Product).filter(models.Product.id == it.product_id).first()
        if prod:
            prod.stock_quantity = (prod.stock_quantity or 0) - it.quantity
            # Permitimos estoque negativo se for o caso
            
    db.delete(entry)
    db.commit()
    return {"message": "Entrada de estoque removida e quantidades revertidas com sucesso"}
