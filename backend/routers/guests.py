from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import asyncio
from sqlalchemy.orm import Session
from typing import List, Optional
import models, schemas
from database import get_db, set_tenant_context
from .auth import get_current_receptionist

router = APIRouter(prefix="/guests", tags=["Guests"])

async def trigger_ai_registration_ack(tenant_id: int, session_id: str, guest_name: str):
    from agents.supervisor_agent import SupervisorAgent
    import logging
    logger = logging.getLogger("AI_ACK")
    try:
        supervisor = SupervisorAgent(tenant_id)
        sys_msg = f"SYSTEM_EVENT: O hóspede {guest_name} acabou de concluir o formulário de cadastro. O ID dele já está no contexto. Agradeça pelo cadastro chamando-o pelo nome e dê o próximo passo do atendimento."
        await asyncio.sleep(1) # Aguarda state_manager terminar de persistir por segurança
        await supervisor.process(sys_msg, session_id)
        logger.info(f"ACK gerado para sessão {session_id}")
    except Exception as e:
        logger.error(f"Falha ao gerar ACK do AI: {e}")

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
    # 0. Ativa RLS context a partir do payload
    set_tenant_context(db, guest_data.tenant_id)

    # 1. Busca hóspede
    existing = db.query(models.Guest).filter(models.Guest.document == guest_data.document).first()
    guest_to_return = None
    
    if existing:
        # Atualiza dados, mas retira o tenant_id para evitar erro se ele tentar injetar algo estranho
        update_dict = guest_data.model_dump(exclude={'tenant_id', 'session_id'})
        for key, value in update_dict.items():
            setattr(existing, key, value)
        db.commit()
        guest_to_return = existing
    else:
        # Como o RLS já ativa o before_flush, não precisa injetar o tenant explicitamente
        # 2. Verifica se o e-mail já existe (evita Erro 500 por UniqueViolation)
        if guest_data.email and db.query(models.Guest).filter(models.Guest.email == guest_data.email).first():
            raise HTTPException(status_code=400, detail="O e-mail informado já está sendo utilizado por outro cadastro.")

        new_guest_dict = guest_data.model_dump(exclude={'tenant_id', 'session_id'})
        new_guest = models.Guest(**new_guest_dict, tenant_id=guest_data.tenant_id)
        db.add(new_guest)
        db.commit()
        guest_to_return = new_guest

    # 3. Dispara Webhook de reconhecimento para o Agente (Se houver session_id)
    if guest_data.session_id:
        try:
            from agents.shared_tools import handle_guest_registration_webhook
            handle_guest_registration_webhook(
                tenant_id=guest_data.tenant_id,
                cpf=guest_data.document,
                session_id=guest_data.session_id
            )
            if guest_to_return:
                background_tasks.add_task(trigger_ai_registration_ack, guest_data.tenant_id, guest_data.session_id, guest_to_return.name)
        except Exception as e:
            print(f"[WEBHOOK ERROR] Falha ao notificar agente: {e}")

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
