"""Rotas públicas de leads (Landing Page)."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.lead import Lead
from app.schemas.lead import LeadCreate, LeadOut
from app.services.email_service import send_lead_gift_email

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead_in: LeadCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> LeadOut:
    logger.info(f"Lead recebido: {lead_in.email}")
    stmt = select(Lead).where(Lead.email == str(lead_in.email))
    existing_lead = await db.scalar(stmt)
    if existing_lead is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email já cadastrado")

    lead = Lead(
        name=lead_in.name,
        email=str(lead_in.email),
        phone=lead_in.phone,
        origin=lead_in.origin,
    )
    db.add(lead)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email já cadastrado"
        ) from exc
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar lead",
        ) from exc

    await db.refresh(lead)
    
    # Enviar e-mail de "presente" em segundo plano
    background_tasks.add_task(send_lead_gift_email, str(lead.email), lead.name)
    
    return lead
