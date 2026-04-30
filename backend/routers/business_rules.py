from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import models, schemas
from database import get_db
from .auth import get_current_admin

router = APIRouter(prefix="/business-rules", tags=["Business Rules"])

@router.get("/", response_model=List[schemas.BusinessRuleResponse])
def list_rules(db: Session = Depends(get_db)):
    from database import set_tenant_context
    set_tenant_context(db, 1) # Define tenant 1 como padrão para visualização pública
    return db.query(models.BusinessRule).all()

@router.post("/", response_model=schemas.BusinessRuleResponse)
def upsert_rule(rule: schemas.BusinessRuleCreate, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    from database import set_tenant_context
    set_tenant_context(db, admin.tenant_id)
    
    # Upsert por nome para simplificar a interface de "Gatilhos"
    existing = db.query(models.BusinessRule).filter(models.BusinessRule.name == rule.name).first()
    if existing:
        for key, value in rule.model_dump().items():
            setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing
    
    new_rule = models.BusinessRule(**rule.model_dump())
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    return new_rule

@router.put("/{rule_id}", response_model=schemas.BusinessRuleResponse)
def update_rule(rule_id: int, rule: schemas.BusinessRuleUpdate, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    from database import set_tenant_context
    set_tenant_context(db, admin.tenant_id)
    
    db_rule = db.query(models.BusinessRule).filter(models.BusinessRule.id == rule_id).first()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    
    for key, value in rule.model_dump(exclude_unset=True).items():
        setattr(db_rule, key, value)
    
    db.commit()
    db.refresh(db_rule)
    return db_rule
