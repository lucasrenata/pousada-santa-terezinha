import logging
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from app.core.config import settings

logger = logging.getLogger(__name__)

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=settings.USE_CREDENTIALS,
    VALIDATE_CERTS=settings.VALIDATE_CERTS,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME
)

async def send_password_reset_email(to_email: str, reset_link: str) -> bool:
    """Envia um e-mail de recuperação de senha."""
    message = MessageSchema(
        subject="Recuperação de senha - ParcerIA",
        recipients=[to_email],
        body=f"""
        Olá,
        
        Você solicitou a redefinição de sua senha no ParcerIA.
        Clique no link abaixo para criar uma nova senha:
        
        {reset_link}
        
        Este link expira em 15 minutos.
        Se você não solicitou isso, ignore este e-mail.
        """,
        subtype=MessageType.plain
    )

    fm = FastMail(conf)
    try:
        await fm.send_message(message)
        logger.info(f"E-mail de recuperação enviado para: {to_email}")
        return True
    except Exception as e:
        # Importante: Não logar MAIL_PASSWORD
        error_msg = f"ERRO CRÍTICO NO ENVIO DE EMAIL para {to_email}: {str(e)}"
        print(error_msg, flush=True)
        logger.error(error_msg)
        return False

async def send_lead_gift_email(to_email: str, name: str) -> bool:
    """Envia o e-mail com o link do presente para o novo lead."""
    gift_link = "https://www.youtube.com/watch?v=D1AUHb7c7wg"
    
    body = f"""
    Olá {name},
    
    Assista essa Aula Especial que preparamos para você. Ficaremos te esperando na Comunidade VisionárIA! 
    
    Acesse aqui: {gift_link}
    
    Há, e não se esqueça! O futuro é agora!
    """

    message = MessageSchema(
        subject="Seu presente chegou!",
        recipients=[to_email],
        body=body,
        subtype=MessageType.plain
    )

    fm = FastMail(conf)
    try:
        await fm.send_message(message)
        logger.info(f"E-mail de presente enviado para lead: {to_email}")
        return True
    except Exception as e:
        error_msg = f"ERRO ao enviar e-mail de presente para {to_email}: {str(e)}"
        print(error_msg, flush=True)
        logger.error(error_msg)
        return False
