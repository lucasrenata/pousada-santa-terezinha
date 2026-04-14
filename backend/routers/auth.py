from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
import os
import bcrypt
import models, schemas
from database import get_db, set_tenant_context
from payments.mercadopago_service import MercadoPagoService

mp_service = MercadoPagoService()

router = APIRouter(tags=["Auth"])

# ... (Previous constants)

@router.post("/validate-field", response_model=schemas.FieldValidationResponse)
def validate_field(request: schemas.FieldValidationRequest, db: Session = Depends(get_db)):
    """Valida se username ou email já estão em uso (Visão Global)"""
    set_tenant_context(db, -1)
    
    if request.field == "username":
        exists = db.query(models.User).filter(models.User.username == request.value).first()
        if exists:
            return {"available": False, "message": "Este nome de usuário já está em uso"}
    
    elif request.field == "email":
        exists = db.query(models.User).filter(models.User.email == request.value).first()
        if exists:
            return {"available": False, "message": "Este e-mail já está cadastrado"}
            
    return {"available": True, "message": "Disponível"}

SECRET_KEY = os.getenv("SECRET_KEY", "dev_change_this_secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# Funções Auxiliares (Usando bcrypt diretamente para evitar bugs de versão)
def verify_password(plain, hashed):
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))

def get_password_hash(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(status_code=401, detail="Credenciais inválidas", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None: raise credentials_exception
    except JWTError: raise credentials_exception
    
    # CRÍTICO: Ativa visão global para encontrar o usuário (RLS bloqueia se tenant_id=0)
    set_tenant_context(db, -1)
    
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None: raise credentials_exception
    
    # Bloqueio em Nível de Sessão (Kill Switch do SaaS)
    if user.role != "superadmin" and user.tenant_id and user.tenant:
        if not user.tenant.is_active:
            raise HTTPException(status_code=403, detail="Ambiente suspenso administrativamente.")
    
    # --- ATIVAÇÃO DO RLS ---
    # SuperAdmin sempre ativa Visão Global (-1) para não ficar preso em um tenant só
    if user.role == "superadmin":
        set_tenant_context(db, -1)
    else:
        set_tenant_context(db, user.tenant_id)
    
    return user

async def get_current_admin(current_user: models.User = Depends(get_current_user)):
    """Acesso nível GERENTE: Pode gerenciar equipe, finanças e configurações."""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Acesso restrito ao Gerente/Administrador")
    return current_user

async def get_current_receptionist(current_user: models.User = Depends(get_current_user)):
    """Acesso nível RECEPCIONISTA: Pode ver reservas, quartos e hóspedes."""
    allowed = ["superadmin", "admin", "recepcionista"]
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Acesso exclusivo para Recepção ou Gerência")
    return current_user

async def get_current_staff(current_user: models.User = Depends(get_current_user)):
    """Acesso nível STAFF/SERVIÇOS: Acesso operacional básico (Limpeza/Manutenção)."""
    allowed = ["superadmin", "admin", "recepcionista", "servico", "faxina", "camareira", "manutencao"]
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Acesso negado para este nível de serviço")
    return current_user

import re

@router.post("/signup", response_model=schemas.SignupResponse)
def signup(request: schemas.SignupRequest, db: Session = Depends(get_db)):
    """Fluxo de Auto-Cadastro: Cria Tenant, Admin e Gera Cobrança Setup (Atômico)"""
    # 0. Ativa o bypass (-1) para validação global e criação do ambiente
    from database import set_tenant_context
    set_tenant_context(db, -1)

    # 1. Valida se usuário já existe
    if db.query(models.User).filter(models.User.username == request.admin_username).first():
        raise HTTPException(status_code=400, detail="Nome de usuário já está em uso")
    
    if db.query(models.User).filter(models.User.email == request.admin_email).first():
        raise HTTPException(status_code=400, detail="E-mail já está em uso")

    # Validação de Senha Forte
    if len(request.admin_password) < 8 or not re.search(r"[a-z]", request.admin_password) or not re.search(r"[A-Z]", request.admin_password) or not re.search(r"[0-9]", request.admin_password) or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", request.admin_password):
        raise HTTPException(status_code=400, detail="A senha deve conter no mínimo 8 caracteres, uma letra maiúscula, uma minúscula, um número e um caractere especial.")
    
    try:
        # 2. Cria o Tenant (Pousada) - INATIVO até o pagamento
        new_tenant = models.Tenant(name=request.pousada_name, is_active=False)
        db.add(new_tenant)
        db.flush() 
        
        # 3. Cria o Usuário Admin vinculado ao Tenant
        new_user = models.User(
            username=request.admin_username, 
            full_name=request.admin_full_name,
            email=request.admin_email,
            password_hash=get_password_hash(request.admin_password), 
            role="admin",
            tenant_id=new_tenant.id
        )
        db.add(new_user)
        db.flush()

        # 4. Busca Configurações da Plataforma (Pelo nome definido no setup) para gerar a cobrança
        platform_tenant = db.query(models.Tenant).filter(models.Tenant.name == "ParcerIA (Plataforma)").first()
        platform_tenant_id = platform_tenant.id if platform_tenant else 1 
        
        platform_config = db.query(models.TenantConfig).filter(models.TenantConfig.tenant_id == platform_tenant_id).first()
        mp_token = platform_config.mp_access_token if platform_config else os.getenv("MERCADOPAGO_ACCESS_TOKEN")
        
        # Busca taxa de setup dinâmica
        fee_setting = db.query(models.SystemSetting).filter(
            models.SystemSetting.tenant_id == platform_tenant_id,
            models.SystemSetting.key == "platform_setup_fee"
        ).first()
        fee_amount = float(fee_setting.value) if fee_setting else 49.90

        payment_url = None
        if mp_token:
            try:
                # Cria preferência para o Setup Tax
                pref = mp_service.create_card_preference(
                    access_token=mp_token,
                    tenant_id=new_tenant.id, 
                    amount=fee_amount,
                    title=f"Taxa de Setup: {request.pousada_name}",
                    metadata={"type": "tenant_setup", "tenant_id": new_tenant.id},
                    back_urls={
                        "success": f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/login?signup=success&id={new_tenant.id}",
                        "failure": f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/signup?error=payment_failed",
                    }
                )
                payment_url = pref.get("response", {}).get("init_point")
            except Exception as mp_err:
                print(f"[MP SIGNUP ERROR] {mp_err}")

        db.commit()
        db.refresh(new_user)
        
        return {
            "user": new_user,
            "payment_url": payment_url,
            "tenant_id": new_tenant.id
        }

    except Exception as e:
        db.rollback()
        error_msg = str(e).lower()
        if "ix_users_username" in error_msg or "username" in error_msg:
            raise HTTPException(status_code=400, detail="Nome de usuário já está em uso")
        if "ix_users_email" in error_msg or "email" in error_msg:
            raise HTTPException(status_code=400, detail="E-mail já está em uso")
        raise HTTPException(status_code=500, detail=f"Erro interno ao criar ambiente: {str(e)}")

@router.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Usuário já existe")
    new_user = models.User(username=user.username, password_hash=get_password_hash(user.password), role=user.role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/token", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # CRÍTICO: Ativa visão global para encontrar o usuário em qualquer tenant
    # Sem isso, o RLS filtra todos os users (tenant_id=0 não existe)
    set_tenant_context(db, -1)
    
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Login incorreto")
        
    # Impedir emissão de token se a Pousada estiver bloqueada
    if user.role != "superadmin" and user.tenant_id and user.tenant:
        if not user.tenant.is_active:
            raise HTTPException(status_code=403, detail="Ambiente suspenso administrativamente. Contate o provedor SaaS.")
            
    token = create_access_token(data={"sub": user.username, "role": user.role, "tenant_id": user.tenant_id})
    return {"access_token": token, "token_type": "bearer", "role": user.role, "tenant_id": user.tenant_id}
