from fastapi import APIRouter, Depends, HTTPException
from .auth import get_current_admin, get_current_staff
from sqlalchemy.orm import Session
from typing import List
import models, schemas
from database import get_db

router = APIRouter(prefix="/rooms", tags=["Rooms"])

@router.post("/", response_model=schemas.RoomResponse)
def create_room(room: schemas.RoomCreate, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    if db.query(models.Room).filter(models.Room.id == room.id).first():
        raise HTTPException(status_code=400, detail="Quarto já existe")
    new_room = models.Room(status=models.RoomStatus.DISPONIVEL, **room.model_dump())
    db.add(new_room)
    db.commit()
    db.refresh(new_room)
    return new_room

@router.get("/", response_model=List[schemas.RoomResponse])
def list_rooms(db: Session = Depends(get_db), user: models.User = Depends(get_current_staff)):
    return db.query(models.Room).all()

@router.get("/by-number/{number}", response_model=schemas.RoomResponse)
def get_room_by_number(number: str, db: Session = Depends(get_db)):
    room = db.query(models.Room).filter(models.Room.id == number).first()
    if not room:
        raise HTTPException(status_code=404, detail="Quarto não encontrado")
    return room

# Rota para camareira
@router.post("/{room_id}/clean")
def mark_clean(room_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_staff)):
    room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not room: raise HTTPException(status_code=404)
    room.status = models.RoomStatus.DISPONIVEL
    room.maintenance_note = None
    db.commit()
    return {"message": "Quarto limpo"}

# Manutenção: marca quarto como MANUTENCAO com observação
@router.post("/{room_id}/maintenance")
def mark_maintenance(room_id: str, note: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_staff)):
    room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not room: raise HTTPException(status_code=404, detail="Quarto não encontrado")
    room.status = models.RoomStatus.MANUTENCAO
    room.maintenance_note = note
    db.commit()
    return {"message": "Quarto em manutenção", "note": note}

# Atualizar quarto
@router.put("/{room_id}", response_model=schemas.RoomResponse)
def update_room(room_id: str, data: schemas.RoomUpdate, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Quarto não encontrado")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(room, key, value)
    
    db.commit()
    db.refresh(room)
    return room

# Excluir quarto
@router.delete("/{room_id}")
def delete_room(room_id: str, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Quarto não encontrado")
    has_bookings = db.query(models.Booking).filter(models.Booking.room_id == room_id).first()
    if has_bookings:
        raise HTTPException(status_code=400, detail="Quarto possui histórico de reservas")
    db.delete(room)
    db.commit()
    return {"message": "Quarto excluído"}
