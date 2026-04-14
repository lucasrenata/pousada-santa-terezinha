from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
import os
import bcrypt
import models, schemas
from database import get_db, set_tenant_context

router = APIRouter(tags=["Auth"])

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
    # Permite acesso para admin e superadmin
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador")
    return current_user

async def get_current_staff(current_user: models.User = Depends(get_current_user)):
    # Permite superadmin, admin e recepcionista para quase tudo
    allowed_roles = ["superadmin", "admin", "recepcionista", "manutencao", "faxina", "camareira"]
    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return current_user

import re

@router.post("/signup", response_model=schemas.UserResponse)
def signup(request: schemas.SignupRequest, db: Session = Depends(get_db)):
    """Fluxo de Auto-Cadastro: Cria Tenant e Admin"""
    # 1. Valida se usuário já existe
    if db.query(models.User).filter(models.User.username == request.admin_username).first():
        raise HTTPException(status_code=400, detail="Nome de usuário já está em uso")
    
    if db.query(models.User).filter(models.User.email == request.admin_email).first():
        raise HTTPException(status_code=400, detail="E-mail já está em uso")

    # Validação de Senha Forte
    if len(request.admin_password) < 8 or not re.search(r"[a-z]", request.admin_password) or not re.search(r"[A-Z]", request.admin_password) or not re.search(r"[0-9]", request.admin_password) or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", request.admin_password):
        raise HTTPException(status_code=400, detail="A senha deve conter no mínimo 8 caracteres, uma letra maiúscula, uma minúscula, um número e um caractere especial.")
    
    # 2. Cria o Tenant (Pousada)
    new_tenant = models.Tenant(name=request.pousada_name)
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)
    
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
    db.commit()
    db.refresh(new_user)
    
    # 4. Configuração Inicial (Ex: Moeda padrão, etc) - Opcional agora
    
    return new_user

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
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Login incorreto")
        
    # Impedir emissão de token se a Pousada estiver bloqueada
    if user.role != "superadmin" and user.tenant_id and user.tenant:
        if not user.tenant.is_active:
            raise HTTPException(status_code=403, detail="Ambiente suspenso administrativamente. Contate o provedor SaaS.")
            
    token = create_access_token(data={"sub": user.username, "role": user.role, "tenant_id": user.tenant_id})
    return {"access_token": token, "token_type": "bearer", "role": user.role, "tenant_id": user.tenant_id}
