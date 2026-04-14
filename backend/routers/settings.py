from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
import models
from database import get_db, set_tenant_context
from typing import Optional
from routers.auth import get_current_admin

router = APIRouter(prefix="/settings", tags=["System Settings"])

class SettingSchema(BaseModel):
    key: str
    value: str
    description: str | None = None

@router.get("/", response_model=List[SettingSchema])
def get_settings(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_admin)):
    # O contexto do tenant já é setado pelo get_current_user/RLS
    return db.query(models.SystemSetting).all()

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
