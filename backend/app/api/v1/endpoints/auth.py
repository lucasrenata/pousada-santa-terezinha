import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Header, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    get_password_hash,
    verify_password,
    verify_password_reset_token,
    create_sso_token,
)
from app.api.deps import get_current_active_user, get_current_admin_user
from app.models.user import User, UserRole, Device
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserOut, PasswordResetRequest, PasswordResetConfirm
from app.services.email_service import send_password_reset_email

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
    x_device_fingerprint: str = Header(None, alias="X-Device-Fingerprint"),
    x_browser_info: str = Header(None, alias="X-Browser-Info"),
) -> Token:
    if len(form_data.password.encode('utf-8')) > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha fornecida é grande demais ou inválida. Limite de 72 bytes excedido."
        )

    try:
        stmt = (
            select(User)
            .where(User.email == form_data.username)
            .options(selectinload(User.devices))
        )
        user = await db.scalar(stmt)
        
        if user is None or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou senha incorretos",
            )

        # 1. Trava de aparelhos (Max 2)
        device_fp = x_device_fingerprint or "unknown"
        browser_info = x_browser_info or "unknown"
        
        device = next(
            (d for d in user.devices if d.device_fingerprint == device_fp), 
            None
        )
        
        if device is None:
            if len(user.devices) >= 2:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Limite de 2 aparelhos atingido. Acesse 'Configurações' em um aparelho já cadastrado para remover um dispositivo antigo."
                )
            # Cadastra novo device
            device = Device(
                user_id=user.id,
                device_fingerprint=device_fp,
                browser_info=browser_info
            )
            db.add(device)
        else:
            # Atualiza o existente
            device.browser_info = browser_info

        # 2. Trava de sessão única
        new_session_id = str(uuid.uuid4())
        user.session_id = new_session_id
        
        await db.commit()
        
        access_token = create_access_token(subject=user.email, session_id=new_session_id)
        return Token(access_token=access_token, token_type="bearer")

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Erro Crítico no Login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao processar o login."
        )


@router.get("/sso-token")
async def get_sso_token(
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Gera um token de SSO de curta duração para ferramentas externas."""
    sso_data = {
        "sub": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
    }
    token = create_sso_token(sso_data)
    return {"sso_token": token}


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    stmt = select(User).where(User.email == user_in.email)
    existing_user = await db.scalar(stmt)
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email já cadastrado")

    user = User(
        email=str(user_in.email),
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=UserRole.STUDENT,
        is_active=True,
    )
    db.add(user)
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
            detail="Erro ao criar usuário",
        ) from exc

    await db.refresh(user)
    return user


@router.post("/password-recovery")
async def password_recovery(
    body: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Solicita recuperação de senha. Sempre retorna a mesma mensagem para prevenir enumeração de usuários."""
    safe_response = {"message": "Se o e-mail existir, um link de recuperação foi enviado."}

    stmt = select(User).where(User.email == str(body.email))
    user = await db.scalar(stmt)

    if user is None:
        return safe_response

    token = create_password_reset_token(email=str(body.email))
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    
    # Log para debug/fallback
    print(f"DEBUG: Link de recuperação gerado para {user.email}: {reset_link}", flush=True)

    try:
        background_tasks.add_task(send_password_reset_email, user.email, reset_link)
    except Exception as e:
        print(f"ERRO AO ADICIONAR TAREFA DE EMAIL: {str(e)}", flush=True)
        logger.error(f"Falha ao agendar e-mail real: {str(e)}")

    return safe_response


@router.post("/reset-password")
async def reset_password(
    body: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Redefine a senha a partir de um token JWT válido de recuperação."""
    email = verify_password_reset_token(body.token)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido ou expirado.",
        )

    stmt = select(User).where(User.email == email)
    user = await db.scalar(stmt)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado.",
        )

    user.hashed_password = get_password_hash(body.new_password)
    await db.commit()

    return {"message": "Senha redefinida com sucesso."}


@router.post("/admin/test-email")
async def admin_test_email(
    to_email: str,
    current_admin: User = Depends(get_current_admin_user),
) -> dict:
    """Endpoint administrativo para testar o envio de e-mail SMTP."""
    success = await send_password_reset_email(to_email, "http://localhost:5179/reset-password?token=test-token")
    if success:
        return {"message": f"E-mail de teste enviado para {to_email}"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao enviar e-mail de teste. Verifique os logs do servidor."
        )
