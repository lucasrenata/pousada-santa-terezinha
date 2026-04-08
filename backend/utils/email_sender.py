import os
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from dotenv import load_dotenv
from pathlib import Path

# Carrega variáveis de ambiente
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

# Configuração do servidor de email
# Se não houver variáveis configuradas, usa valores dummy para não quebrar a inicialização
conf = ConnectionConfig(
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "user@example.com"),
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "password"),
    MAIL_FROM = os.getenv("MAIL_FROM", "noreply@pousada.com"),
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587)),
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_FROM_NAME = "ParcerIA Hotelaria",
    
    # --- AQUI ESTAVA O ERRO, ESTES SÃO OS NOMES NOVOS ---
    MAIL_STARTTLS = True,  # Substitui MAIL_TLS
    MAIL_SSL_TLS = False,  # Substitui MAIL_SSL
    # ----------------------------------------------------
    
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

async def send_booking_confirmation(to_email: EmailStr, guest_name: str, room_number: str, checkin: str, checkout: str):
    """
    Envia email de confirmação de reserva.
    Só funcionará se as variáveis de ambiente estiverem corretas no .env
    """
    if os.getenv("MAIL_USERNAME") == "user@example.com":
        print("⚠️ Email não configurado no .env. Pulando envio.")
        return

    html = f"""
    <h3>Olá, {guest_name}!</h3>
    <p>Sua reserva na <b>ParcerIA Hotelaria</b> foi confirmada com sucesso.</p>
    <ul>
        <li><b>Quarto:</b> {room_number}</li>
        <li><b>Check-in:</b> {checkin}</li>
        <li><b>Check-out:</b> {checkout}</li>
    </ul>
    <p>Estamos ansiosos para recebê-lo!</p>
    """

    message = MessageSchema(
        subject="Confirmação de Reserva - ParcerIA",
        recipients=[to_email],
        body=html,
        subtype=MessageType.html
    )

    fm = FastMail(conf)
    try:
        await fm.send_message(message)
        print(f"📧 Email enviado para {to_email}")
    except Exception as e:
        print(f"❌ Erro ao enviar email: {e}")
