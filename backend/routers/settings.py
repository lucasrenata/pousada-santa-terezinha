from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
import models
from database import get_db, set_tenant_context
from typing import Optional

router = APIRouter(prefix="/settings", tags=["System Settings"])

class SettingSchema(BaseModel):
    key: str
    value: str
    description: str | None = None

@router.get("/", response_model=List[SettingSchema])
def get_settings(tenant_id: Optional[int] = None, db: Session = Depends(get_db)):
    if tenant_id:
        set_tenant_context(db, tenant_id)
    return db.query(models.SystemSetting).all()

@router.post("/")
def update_setting(setting: SettingSchema, tenant_id: Optional[int] = None, db: Session = Depends(get_db)):
    if tenant_id:
        set_tenant_context(db, tenant_id)
    db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == setting.key).first()
    if db_setting:
        db_setting.value = setting.value
        db_setting.description = setting.description
    else:
        new_s = models.SystemSetting(key=setting.key, value=setting.value, description=setting.description)
        db.add(new_s)
    db.commit()
    return {"message": "Salvo"}
