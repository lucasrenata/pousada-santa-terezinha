from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from pydantic import BaseModel
from typing import Optional
from datetime import date

router = APIRouter(prefix="/events", tags=["eventos"])

class EventCreate(BaseModel):
    name: str
    start_date: date
    end_date: date
    location: Optional[str] = "Canção Nova - Cachoeira Paulista/SP"
    description: Optional[str] = None
    color: Optional[str] = "#6366f1"

class EventUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    location: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None

@router.get("/")
def list_events(year: int = 2026, db: Session = Depends(get_db)):
    events = db.query(models.Event).filter(
        models.Event.start_date >= date(year, 1, 1),
        models.Event.start_date <= date(year, 12, 31)
    ).order_by(models.Event.start_date.asc()).all()
    return [{
        "id": e.id, "name": e.name, 
        "start_date": str(e.start_date), "end_date": str(e.end_date),
        "location": e.location, "description": e.description, "color": e.color
    } for e in events]

@router.post("/")
def create_event(data: EventCreate, db: Session = Depends(get_db)):
    event = models.Event(**data.dict())
    db.add(event)
    db.commit()
    db.refresh(event)
    return {"id": event.id, "name": event.name}

@router.put("/{event_id}")
def update_event(event_id: int, data: EventUpdate, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    for key, value in data.dict(exclude_unset=True).items():
        if value is not None:
            setattr(event, key, value)
    db.commit()
    db.refresh(event)
    return {"id": event.id, "name": event.name, "start_date": str(event.start_date)}

@router.delete("/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    db.delete(event)
    db.commit()
    return {"message": "Evento excluído"}

@router.post("/seed")
def seed_events(year: int = 2026, db: Session = Depends(get_db)):
    """Popula o banco com o calendário Canção Nova para o ano informado."""
    # Remove eventos existentes do ano para evitar duplicatas
    db.query(models.Event).filter(
        models.Event.start_date >= date(year, 1, 1),
        models.Event.start_date <= date(year, 12, 31)
    ).delete()
    db.commit()

    events_data = [
        # Janeiro
        ("Acampamento Revolução Jesus", date(year, 1, 7), date(year, 1, 11), "#ef4444"),
        ("Acampamento para as Famílias", date(year, 1, 15), date(year, 1, 18), "#f97316"),
        ("4º Encontro Nacional do Exército de São Miguel", date(year, 1, 29), date(year, 2, 1), "#eab308"),
        # Fevereiro
        ("Rebanhão (Carnaval da Canção Nova)", date(year, 2, 13), date(year, 2, 18), "#ef4444"),
        # Março
        ("Acampamento de Cura e Libertação", date(year, 3, 13), date(year, 3, 15), "#8b5cf6"),
        ("Acampamento de São José", date(year, 3, 19), date(year, 3, 22), "#6366f1"),
        # Abril
        ("Acampamento de Semana Santa (Tríduo Pascal)", date(year, 4, 2), date(year, 4, 5), "#ef4444"),
        ("Festa da Divina Misericórdia", date(year, 4, 9), date(year, 4, 12), "#ec4899"),
        ("Acampamento Geral", date(year, 4, 16), date(year, 4, 19), "#6366f1"),
        ("Acampamento Geral", date(year, 4, 24), date(year, 4, 26), "#6366f1"),
        ("Acampamento de Oração", date(year, 4, 30), date(year, 5, 3), "#14b8a6"),
        # Maio
        ("Aprofundamento: Sexualidade e Educação dos Filhos", date(year, 5, 15), date(year, 5, 17), "#f97316"),
        ("Acampamento de Oração", date(year, 5, 29), date(year, 5, 31), "#14b8a6"),
        # Junho
        ("Acampamento de Corpus Christi", date(year, 6, 4), date(year, 6, 7), "#eab308"),
        ("Aprofundamento: A libertação dos espíritos malignos", date(year, 6, 12), date(year, 6, 14), "#8b5cf6"),
        # Julho
        ("Acampamento PHN 2026 (Alvejados)", date(year, 7, 8), date(year, 7, 12), "#ef4444"),
        ("Acampamento para Casais", date(year, 7, 24), date(year, 7, 26), "#ec4899"),
        # Agosto
        ("Acampamento para as Famílias", date(year, 8, 14), date(year, 8, 16), "#f97316"),
        ("Acampamento no Combate da Oração", date(year, 8, 22), date(year, 8, 24), "#14b8a6"),
        # Setembro
        ("Profecia do Avivamento", date(year, 9, 21), date(year, 9, 23), "#eab308"),
        ("Acampamento de São Miguel Arcanjo", date(year, 9, 25), date(year, 9, 28), "#6366f1"),
        # Outubro
        ("Acampamento de Cura e Libertação", date(year, 10, 3), date(year, 10, 5), "#8b5cf6"),
        ("Acampamento Fé Católica (Frei Gilson e Prof. Felipe Aquino)", date(year, 10, 25), date(year, 10, 27), "#ef4444"),
        ("Acampamento: A Cura dos Traumas da Morte", date(year, 10, 31), date(year, 11, 2), "#8b5cf6"),
        # Novembro
        ("Acampamento Canção Nova Sertaneja", date(year, 11, 28), date(year, 11, 30), "#f97316"),
        # Dezembro
        ("Hosana Brasil 2026", date(year, 12, 10), date(year, 12, 13), "#ef4444"),
        ("Santa Missa da Virada e Réveillon", date(year, 12, 31), date(year, 12, 31), "#eab308"),
    ]

    for name, start, end, color in events_data:
        db.add(models.Event(
            name=name, start_date=start, end_date=end,
            location="Canção Nova - Cachoeira Paulista/SP", color=color
        ))
    db.commit()
    return {"message": f"{len(events_data)} eventos inseridos para {year}"}
