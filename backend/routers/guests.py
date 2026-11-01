from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import asyncio
from sqlalchemy.orm import Session
from typing import List, Optional
import models, schemas
from database import get_db, set_tenant_context
from .auth import get_current_receptionist

router = APIRouter(prefix="/guests", tags=["Guests"])

async def trigger_ai_registration_ack(tenant_id: int, session_id: str, guest_name: str):
    # No-op: IA desativada
    pass

@router.get("/public/lookup", response_model=Optional[schemas.GuestResponse])
def lookup_guest_public(document: str, tenant_id: int, db: Session = Depends(get_db)):
    # Usa visão global (-1) para garantir que hóspedes com tenant_id=0 (cadastros legados)
    # ou com outro tenant sejam encontrados pelo documento/nome. O CPF é único por natureza.
    set_tenant_context(db, -1)
    clean_doc = "".join(filter(str.isdigit, document))
    guest = db.query(models.Guest).filter(
        (models.Guest.document == document) | 
        (models.Guest.document == clean_doc) |
        (models.Guest.name.ilike(f"%{document}%"))
    ).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Hóspede não encontrado")
    return guest

@router.post("/", response_model=schemas.GuestResponse)
def create_guest(guest: schemas.GuestCreate, db: Session = Depends(get_db), current_user = Depends(get_current_receptionist)):
    set_tenant_context(db, current_user.tenant_id)
    if db.query(models.Guest).filter(models.Guest.document == guest.document).first():
        raise HTTPException(status_code=400, detail="Este CPF/RG já está cadastrado no sistema.")
    
    if guest.email and db.query(models.Guest).filter(models.Guest.email == guest.email).first():
        raise HTTPException(status_code=400, detail="Este e-mail já está sendo utilizado por outro hóspede.")
    
    new_guest = models.Guest(**guest.model_dump(), tenant_id=current_user.tenant_id)
    db.add(new_guest)
    db.commit()
    # db.refresh(new_guest)
    return new_guest

@router.post("/public", response_model=schemas.GuestResponse)
def create_guest_public(guest_data: schemas.GuestPublicCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # 0. Usa visão global para localizar hóspede existente por documento,
    # independente do tenant_id armazenado (cobre cadastros legados com tenant_id=0)
    set_tenant_context(db, -1)

    # 1. Busca hóspede por documento
    clean_doc = "".join(filter(str.isdigit, guest_data.document)) if guest_data.document else ""
    existing = db.query(models.Guest).filter(
        (models.Guest.document == guest_data.document) |
        (models.Guest.document == clean_doc)
    ).first()
    guest_to_return = None
    
    if existing:
        # Previne erro se tentar alterar para um e-mail em uso por outro CPF
        if guest_data.email and existing.email != guest_data.email:
            if db.query(models.Guest).filter(models.Guest.email == guest_data.email, models.Guest.id != existing.id).first():
                raise HTTPException(status_code=400, detail="O e-mail informado já está sendo utilizado por outro cadastro.")
                
        # Atualiza dados do hóspede existente
        update_dict = guest_data.model_dump(exclude={'tenant_id', 'session_id'})
        for key, value in update_dict.items():
            setattr(existing, key, value)
        # Corrige o tenant_id se estava como 0 (legado)
        if existing.tenant_id == 0 and guest_data.tenant_id and guest_data.tenant_id > 0:
            existing.tenant_id = guest_data.tenant_id
        db.commit()
        guest_to_return = existing
    else:
        # Muda para o tenant correto antes de criar novo hóspede
        set_tenant_context(db, guest_data.tenant_id)

        # 2. Verifica se o e-mail já existe (evita Erro 500 por UniqueViolation)
        if guest_data.email and db.query(models.Guest).filter(models.Guest.email == guest_data.email).first():
            raise HTTPException(status_code=400, detail="O e-mail informado já está sendo utilizado por outro cadastro.")

        new_guest_dict = guest_data.model_dump(exclude={'tenant_id', 'session_id'})
        new_guest = models.Guest(**new_guest_dict, tenant_id=guest_data.tenant_id)
        db.add(new_guest)
        db.commit()
        guest_to_return = new_guest

    # 3. Notificação do Agente removida (IA desativada)
    return guest_to_return

@router.get("/", response_model=List[schemas.GuestResponse])
def list_guests(q: Optional[str] = None, db: Session = Depends(get_db), current_user = Depends(get_current_receptionist)):
    set_tenant_context(db, current_user.tenant_id)
    query = db.query(models.Guest)
    if q:
        query = query.filter(
            (models.Guest.name.ilike(f"%{q}%")) | 
            (models.Guest.document.ilike(f"%{q}%")) |
            (models.Guest.email.ilike(f"%{q}%"))
        )
    return query.all()

@router.get("/{guest_id}", response_model=schemas.GuestResponse)
def get_guest(guest_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_receptionist)):
    set_tenant_context(db, current_user.tenant_id)
    guest = db.query(models.Guest).filter(models.Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Hóspede não encontrado")
    return guest

@router.put("/{guest_id}", response_model=schemas.GuestResponse)
def update_guest(guest_id: int, data: schemas.GuestUpdate, db: Session = Depends(get_db), current_user = Depends(get_current_receptionist)):
    set_tenant_context(db, current_user.tenant_id)
    guest = db.query(models.Guest).filter(models.Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Hóspede não encontrado")
    
    for key, value in data.model_dump().items():
        setattr(guest, key, value)
    
    db.commit()
    # db.refresh(guest)
    return guest

@router.delete("/{guest_id}")
def delete_guest(guest_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_receptionist)):
    set_tenant_context(db, current_user.tenant_id)
    guest = db.query(models.Guest).filter(models.Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Hóspede não encontrado")
    db.delete(guest)
    db.commit()
    return {"message": "Hóspede removido"}
