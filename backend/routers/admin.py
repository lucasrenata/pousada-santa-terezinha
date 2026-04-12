from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import models, schemas
from database import get_db
from .auth import get_current_admin, get_password_hash

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/users", response_model=list[schemas.UserResponse])
def list_users(db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    # Isolar a conta da Plataforma (Superadmin) da lista de colaboradores da pousada
    return db.query(models.User).filter(models.User.role != "superadmin").all()

import re

@router.post("/users", response_model=schemas.UserResponse)
def create_system_user(user: schemas.UserCreate, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Usuário já existe")
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

    # Validação de Senha Forte
    if len(user.password) < 8 or not re.search(r"[a-z]", user.password) or not re.search(r"[A-Z]", user.password) or not re.search(r"[0-9]", user.password) or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", user.password):
        raise HTTPException(status_code=400, detail="A senha deve conter no mínimo 8 caracteres, uma letra maiúscula, uma minúscula, um número e um caractere especial.")

    new_user = models.User(
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        password_hash=get_password_hash(user.password),
        role=user.role,
        tenant_id=admin.tenant_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.put("/users/{user_id}", response_model=schemas.UserResponse)
def update_user(user_id: int, user_update: schemas.UserUpdate, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    if user_update.email and user_update.email != user.email:
        if db.query(models.User).filter(models.User.email == user_update.email).first():
            raise HTTPException(status_code=400, detail="E-mail já cadastrado")
            
    if user_update.password:
        if len(user_update.password) < 8 or not re.search(r"[a-z]", user_update.password) or not re.search(r"[A-Z]", user_update.password) or not re.search(r"[0-9]", user_update.password) or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", user_update.password):
            raise HTTPException(status_code=400, detail="A senha deve conter no mínimo 8 caracteres, uma letra maiúscula, uma minúscula, um número e um caractere especial.")
        user.password_hash = get_password_hash(user_update.password)

    if user_update.full_name is not None:
        user.full_name = user_update.full_name
    if user_update.email is not None:
        user.email = user_update.email
    if user_update.role is not None:
        # Check rule to not downgrade the main admin
        if user.username == "admin" and user_update.role != "admin":
             raise HTTPException(status_code=400, detail="Não é possível alterar o nível de acesso do administrador principal")
        user.role = user_update.role

    db.commit()
    db.refresh(user)
    return user

@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    if user.username == "admin" or user.role == "superadmin":
        raise HTTPException(status_code=400, detail="Não é possível deletar contas matriz de administração")
    
    db.delete(user)
    db.commit()
    return {"message": "Usuário deletado com sucesso"}
