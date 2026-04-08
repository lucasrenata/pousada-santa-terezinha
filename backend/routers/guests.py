from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import models, schemas
from database import get_db

router = APIRouter(prefix="/guests", tags=["Guests"])

@router.post("/", response_model=schemas.GuestResponse)
def create_guest(guest: schemas.GuestCreate, db: Session = Depends(get_db)):
    if db.query(models.Guest).filter(models.Guest.document == guest.document).first():
        raise HTTPException(status_code=400, detail="CPF/RG já cadastrado")
    
    new_guest = models.Guest(**guest.model_dump())
    db.add(new_guest)
    db.commit()
    db.refresh(new_guest)
    return new_guest

@router.get("/", response_model=List[schemas.GuestResponse])
def list_guests(q: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Guest)
    if q:
        query = query.filter(
            (models.Guest.name.ilike(f"%{q}%")) | 
            (models.Guest.document.ilike(f"%{q}%")) |
            (models.Guest.email.ilike(f"%{q}%"))
        )
    return query.all()

@router.get("/{guest_id}", response_model=schemas.GuestResponse)
def get_guest(guest_id: int, db: Session = Depends(get_db)):
    guest = db.query(models.Guest).filter(models.Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Hóspede não encontrado")
    return guest

@router.put("/{guest_id}", response_model=schemas.GuestResponse)
def update_guest(guest_id: int, data: schemas.GuestCreate, db: Session = Depends(get_db)):
    guest = db.query(models.Guest).filter(models.Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Hóspede não encontrado")
    
    for key, value in data.model_dump().items():
        setattr(guest, key, value)
    
    db.commit()
    db.refresh(guest)
    return guest

@router.delete("/{guest_id}")
def delete_guest(guest_id: int, db: Session = Depends(get_db)):
    guest = db.query(models.Guest).filter(models.Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Hóspede não encontrado")
    db.delete(guest)
    db.commit()
    return {"message": "Hóspede removido"}
