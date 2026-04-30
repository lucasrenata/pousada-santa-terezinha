from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
import models, schemas
from database import get_db, set_tenant_context
from typing import Optional
from routers.auth import get_current_admin

router = APIRouter(prefix="/settings", tags=["System Settings"])

class SettingSchema(BaseModel):
    key: str
    value: str
    description: str | None = None

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    cnpj: Optional[str] = None
    address: Optional[str] = None

@router.get("/", response_model=List[SettingSchema])
def get_settings(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_admin)):
    # O contexto do tenant já é setado pelo get_current_user/RLS
    return db.query(models.SystemSetting).all()

@router.get("/public/{tenant_id}", response_model=List[SettingSchema])
def get_public_settings(tenant_id: int, db: Session = Depends(get_db)):
    """Retorna apenas configurações não sensíveis para o portal do hóspede."""
    set_tenant_context(db, tenant_id)
    # Lista branca de chaves seguras para exposição pública
    public_keys = ['pousada_name', 'pousada_checkin_time', 'pousada_checkout_time', 'pousada_logo_url', 'ai_receptionist_name']
    return db.query(models.SystemSetting).filter(models.SystemSetting.key.in_(public_keys)).all()

@router.get("/public/tenant/{tenant_id}", response_model=schemas.TenantPublicResponse)
def get_public_tenant_info(tenant_id: int, db: Session = Depends(get_db)):
    """Retorna os dados públicos oficiais da pousada para o chat do hóspede."""
    set_tenant_context(db, tenant_id)
    return db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()

@router.post("/")
def update_setting(setting: SettingSchema, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_admin)):
    db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == setting.key).first()
    if db_setting:
        db_setting.value = setting.value
        db_setting.description = setting.description
    else:
        new_s = models.SystemSetting(key=setting.key, value=setting.value, description=setting.description)
        db.add(new_s)
    db.commit()
    return {"message": "Salvo"}

# --- GESTÃO DOS DADOS DA POUSADA (TENANT) ---

@router.get("/tenant", response_model=schemas.TenantResponse)
def get_tenant_info(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_admin)):
    """Busca os dados oficiais da pousada (Nome, CNPJ, Endereço)"""
    return db.query(models.Tenant).filter(models.Tenant.id == current_user.tenant_id).first()

@router.patch("/tenant", response_model=schemas.TenantResponse)
def update_tenant_info(payload: TenantUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_admin)):
    """Atualiza os dados oficiais da pousada"""
    tenant = db.query(models.Tenant).filter(models.Tenant.id == current_user.tenant_id).first()
    if payload.name is not None: tenant.name = payload.name
    if payload.cnpj is not None: tenant.cnpj = payload.cnpj
    if payload.address is not None: tenant.address = payload.address
    db.commit()
    db.refresh(tenant)
    return tenant
