from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db, set_tenant_context
from .auth import get_current_user
import models
import psutil
from typing import List, Dict, Any

router = APIRouter(prefix="/super", tags=["SuperAdmin Console"])

@router.get("/public/pricing")
def get_public_pricing(db: Session = Depends(get_db)):
    """Endpoint público para expor a taxa de setup configurada pelo SuperAdmin"""
    set_tenant_context(db, -1)
    platform_tenant = db.query(models.Tenant).filter(models.Tenant.name == "ParcerIA (Plataforma)").first()
    platform_tenant_id = platform_tenant.id if platform_tenant else 1
    
    fee_setting = db.query(models.SystemSetting).filter(
        models.SystemSetting.tenant_id == platform_tenant_id,
        models.SystemSetting.key == "platform_setup_fee"
    ).first()
    setup_fee = float(fee_setting.value) if fee_setting else 450.00
    
    return {"setup_fee": setup_fee}

# Dependência para validar se é SuperAdmin
async def get_current_superadmin(current_user: models.User = Depends(get_current_user)):
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Acesso restrito ao SuperAdmin da plataforma")
    return current_user

import schemas
from .auth import get_password_hash
import re

@router.get("/profile", response_model=schemas.UserResponse, dependencies=[Depends(get_current_superadmin)])
def get_superadmin_profile(current_user: models.User = Depends(get_current_superadmin)):
    """Retorna os dados do Superadmin logado"""
    return current_user

@router.put("/profile", response_model=schemas.UserResponse, dependencies=[Depends(get_current_superadmin)])
def update_superadmin_profile(user_update: schemas.UserUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_superadmin)):
    """Atualiza o perfil da conta matriz da plataforma SaaS"""
    if user_update.email and user_update.email != current_user.email:
        if db.query(models.User).filter(models.User.email == user_update.email).first():
            raise HTTPException(status_code=400, detail="E-mail já está em uso por outra conta")
            
    if user_update.password:
        if len(user_update.password) < 8 or not re.search(r"[a-z]", user_update.password) or not re.search(r"[A-Z]", user_update.password) or not re.search(r"[0-9]", user_update.password) or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", user_update.password):
            raise HTTPException(status_code=400, detail="A senha deve conter no mínimo 8 caracteres, uma letra maiúscula, uma minúscula, um número e um caractere especial.")
        current_user.password_hash = get_password_hash(user_update.password)

    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
    if user_update.email is not None:
        current_user.email = user_update.email

    db.commit()
    db.refresh(current_user)
    return current_user

@router.get("/metrics/system", dependencies=[Depends(get_current_superadmin)])
def get_system_metrics():
    """Retorna métricas de Hardware (RAM) do Servidor"""
    mem = psutil.virtual_memory()
    return {
        "ram_total": round(mem.total / (1024**3), 2),     # GB
        "ram_used": round(mem.used / (1024**3), 2),       # GB
        "ram_percent": mem.percent,
        "cpu_percent": psutil.cpu_percent(interval=1),
        "status": "Healthy" if mem.percent < 90 else "Critical"
    }

@router.get("/metrics/storage", dependencies=[Depends(get_current_superadmin)])
def get_storage_metrics(db: Session = Depends(get_db)):
    """Calcula o peso físico (MB) consumido por cada Tenant (Sob Demanda)"""
    # Ativa bypass de RLS para ver tudo
    set_tenant_context(db, -1)
    
    tables = [
        'users', 'rooms', 'guests', 'products', 'bookings', 
        'companions', 'consumptions', 'revenues', 'business_rules', 
        'chat_messages', 'stock_entries', 'stock_entry_items', 
        'settings', 'events'
    ]
    
    usage_by_tenant = {}
    
    try:
        for table in tables:
            # Query para estimar tamanho por tenant nesta tabela
            # pg_column_size(t.*) pega o tamanho da linha inteira
            query = text(f"SELECT tenant_id, sum(pg_column_size(t.*)) as size FROM {table} t GROUP BY tenant_id")
            results = db.execute(query).fetchall()
            
            for tid, size in results:
                if tid not in usage_by_tenant:
                    usage_by_tenant[tid] = 0
                usage_by_tenant[tid] += size or 0
                
        # Converte para MB e formata resposta
        tenants = db.query(models.Tenant).all()
        report = []
        for t in tenants:
            bytes_used = usage_by_tenant.get(t.id, 0)
            report.append({
                "tenant_id": t.id,
                "name": t.name,
                "size_mb": round(bytes_used / (1024 * 1024), 4),
                "is_active": t.is_active
            })
            
        return {
            "platform_total_mb": round(sum(usage_by_tenant.values()) / (1024 * 1024), 4),
            "tenants": report
        }
    except Exception as e:
        print(f"Erro ao calcular storage: {e}")
        raise HTTPException(status_code=500, detail="Erro ao calcular métricas de armazenamento")

@router.get("/tenants", dependencies=[Depends(get_current_superadmin)])
def list_tenants(db: Session = Depends(get_db)):
    """Lista detalhada de pousadas para gestão (Exclui a Matriz)"""
    set_tenant_context(db, -1)
    tenants = db.query(models.Tenant).filter(models.Tenant.name != "ParcerIA (Plataforma)").order_by(models.Tenant.created_at.desc()).all()
    
    # Adicionamos contagem rápida de usuários por tenant
    report = []
    for t in tenants:
        user_count = db.query(models.User).filter(models.User.tenant_id == t.id).count()
        report.append({
            "id": t.id,
            "name": t.name,
            "created_at": t.created_at,
            "is_active": t.is_active,
            "user_count": user_count
        })
    return report

@router.post("/tenants/{tenant_id}/toggle", dependencies=[Depends(get_current_superadmin)])
def toggle_tenant(tenant_id: int, db: Session = Depends(get_db)):
    """Ativa/Desativa uma pousada (Kill Switch)"""
    set_tenant_context(db, -1)
    tenant = db.query(models.Tenant).get(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    
    tenant.is_active = not tenant.is_active
    db.commit()
    return {"id": tenant.id, "new_active_status": tenant.is_active}

@router.delete("/tenants/{tenant_id}", dependencies=[Depends(get_current_superadmin)])
def delete_tenant(tenant_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_superadmin)):
    """Remove permanentemente uma pousada e todos os seus dados"""
    set_tenant_context(db, -1)
    
    # Proteção: não pode deletar a Matriz/Plataforma
    tenant = db.query(models.Tenant).get(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    
    if tenant.name == "ParcerIA (Plataforma)":
        raise HTTPException(status_code=403, detail="Não é permitido remover o Tenant da Plataforma.")
    
    # Proteção: não pode deletar o tenant do próprio superadmin logado
    if current_user.tenant_id == tenant_id:
        raise HTTPException(status_code=403, detail="Você não pode remover o seu próprio tenant.")

    # Exclusão em cascata (dados do tenant) usando context global
    set_tenant_context(db, -1)
    
    # Remove registros de dados em ordem (respeitando FKs)
    db.query(models.SystemSetting).filter(models.SystemSetting.tenant_id == tenant_id).delete()
    db.query(models.TenantConfig).filter(models.TenantConfig.tenant_id == tenant_id).delete()
    db.query(models.Revenue).filter(models.Revenue.tenant_id == tenant_id).delete(synchronize_session=False)
    db.query(models.User).filter(models.User.tenant_id == tenant_id).delete(synchronize_session=False)
    db.delete(tenant)
    db.commit()
    
    return {"success": True, "deleted_tenant_id": tenant_id}

@router.get("/config", dependencies=[Depends(get_current_superadmin)])
def get_platform_config(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_superadmin)):
    """Busca as chaves de faturamento e taxas da plataforma (Master Tenant)"""
    if not current_user.tenant_id:
         raise HTTPException(status_code=400, detail="Usuário SuperAdmin não vinculado a um Tenant de plataforma.")
    
    # Busca a taxa de setup nos SystemSettings do Master
    fee_setting = db.query(models.SystemSetting).filter(
        models.SystemSetting.tenant_id == current_user.tenant_id,
        models.SystemSetting.key == "platform_setup_fee"
    ).first()
    fee = float(fee_setting.value) if fee_setting else 450.00

    config = db.query(models.TenantConfig).filter(models.TenantConfig.tenant_id == current_user.tenant_id).first()
    if not config:
        return {"mp_access_token": "", "mp_public_key": "", "manual_pix_key": "", "platform_setup_fee": fee}
    
    return {
        "mp_access_token": config.mp_access_token or "",
        "mp_public_key": config.mp_public_key or "",
        "manual_pix_key": config.manual_pix_key or "",
        "platform_setup_fee": fee
    }

@router.put("/config", dependencies=[Depends(get_current_superadmin)])
def update_platform_config(config_data: Dict[str, Any], db: Session = Depends(get_db), current_user: models.User = Depends(get_current_superadmin)):
    """Atualiza as chaves de faturamento e taxas da plataforma"""
    if not current_user.tenant_id:
         raise HTTPException(status_code=400, detail="Usuário SuperAdmin não vinculado a um Tenant de plataforma.")
    
    # 1. Atualiza TenantConfig (MP Keys e PIX)
    config = db.query(models.TenantConfig).filter(models.TenantConfig.tenant_id == current_user.tenant_id).first()
    if not config:
        config = models.TenantConfig(tenant_id=current_user.tenant_id)
        db.add(config)
    
    if "mp_access_token" in config_data: config.mp_access_token = config_data["mp_access_token"]
    if "mp_public_key" in config_data: config.mp_public_key = config_data["mp_public_key"]
    if "manual_pix_key" in config_data: config.manual_pix_key = config_data["manual_pix_key"]
    
    # 2. Atualiza Taxa de Setup nos SystemSettings do Master
    if "platform_setup_fee" in config_data:
        fee_key = "platform_setup_fee"
        fee_value = str(config_data["platform_setup_fee"])
        
        setting = db.query(models.SystemSetting).filter(
            models.SystemSetting.tenant_id == current_user.tenant_id,
            models.SystemSetting.key == fee_key
        ).first()
        
        if setting:
            setting.value = fee_value
        else:
            new_setting = models.SystemSetting(
                tenant_id=current_user.tenant_id,
                key=fee_key,
                value=fee_value,
                description="Taxa de configuração cobrada de novas pousadas no Signup"
            )
            db.add(new_setting)

    db.commit()
    return {"success": True}
