import asyncio
from fastapi import APIRouter, Request, BackgroundTasks
from services.whatsapp import WhatsAppService
from database import SessionLocal
from routers.chat import save_message, get_db_history
from agents.admin_agent import handle_admin_query

router = APIRouter(prefix="/webhook/whatsapp", tags=["Webhooks"])

async def process_whatsapp_message(payload: dict):
    """
    Processa a mensagem recebida da Evolution API em background.
    """
    event = payload.get("event")
    
    # Processa apenas o evento de novas mensagens recebidas
    if event not in ["messages.upsert", "messages.receive"]:
        return

    data = payload.get("data", {})
    
    # Dependendo da versão da Evolution, `data` pode ser uma lista ou dict único.
    # Vamos assumir o padrão onde `data` tem o objeto da mensagem diretamente ou `messages` list.
    message_data = data.get("message", data) if isinstance(data, dict) else data

    # Se message_data for a lista original do bailey's
    if isinstance(message_data, dict) and "messages" in message_data:
        message_data = message_data["messages"][0]

    # Verifica se a mensagem foi enviada por nós mesmos (ignorar eco)
    key = message_data.get("key", {})
    if key.get("fromMe", False):
        return

    remote_jid = key.get("remoteJid", "")
    if not remote_jid or "@g.us" in remote_jid:
        # Ignora grupos ou ausência de remetente (por enquanto)
        return

    # Extrai o número formatado
    user_id = remote_jid.split("@")[0]
    
    msg_content_obj = message_data.get("message", {})
    if not msg_content_obj:
        return

    # Identifica o tipo de mensagem
    message_type = "unknown"
    content = None
    
    whatsapp_service = WhatsAppService()

    if "conversation" in msg_content_obj:
        message_type = "text"
        content = msg_content_obj["conversation"]
    elif "extendedTextMessage" in msg_content_obj:
        message_type = "text"
        content = msg_content_obj["extendedTextMessage"].get("text", "")
    elif "imageMessage" in msg_content_obj:
        message_type = "image"
        # Precisaremos baixar a mídia via Evolution
        # No payload do webhook da Evolution, se base64 estiver ativado, vem na raiz:
        if "base64" in data:
            import base64
            b64_str = data["base64"]
            if "," in b64_str: b64_str = b64_str.split(",")[1]
            content = base64.b64decode(b64_str)
        else:
            # Chama serviço pra baixar o base64 (Depende de versão Evolution > 2.0)
            content = await whatsapp_service.download_media(msg_content_obj)
    elif "audioMessage" in msg_content_obj:
        message_type = "audio"
        if "base64" in data:
            import base64
            b64_str = data["base64"]
            if "," in b64_str: b64_str = b64_str.split(",")[1]
            content = base64.b64decode(b64_str)
        else:
            content = await whatsapp_service.download_media(msg_content_obj)

    if not content and message_type != "unknown":
        print(f"Não foi possível extrair conteúdo da mensagem do usuário {user_id}.")
        return

    # Se não for texto, por enquanto avisamos que só suportamos texto
    if message_type != "text":
        error_msg = "Desculpe, por enquanto só consigo entender mensagens de texto. Audio e Imagem em breve!"
        await whatsapp_service.send_text(number=user_id, text=error_msg)
        return

    # Injeta contexto do banco de dados e chama o Agente Admin
    db = SessionLocal()
    try:
        # Usa o próprio número do usuário como session_id para o chat
        session_id = f"wa_{user_id}"
        
        # Salva a mensagem do usuário
        save_message(session_id, "user", str(content), db)
        
        # Busca o histórico do admin
        history = await get_db_history(session_id, db)
        
        # Chama o Agente Admin
        result = await handle_admin_query(str(content), history[:-1], db)
        response_text = result.get("response", "Ocorreu um erro ao processar sua requisição.")
        
        # Salva a resposta da IA
        save_message(session_id, "assistant", response_text, db)
        
        # Envia a resposta de volta ao WhatsApp
        await whatsapp_service.send_text(number=user_id, text=response_text)
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Erro ao processar mensagem com o agente admin para o usuário {user_id}: {e}")
    finally:
        db.close()


@router.post("")
async def receive_whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint principal para receber os eventos da Evolution API.
    A Evolution tem timeouts muito curtos, então delegamos o processamento 
    para o BackgroundTasks e retornamos 200 OK imediatamente.
    """
    try:
        payload = await request.json()
        background_tasks.add_task(process_whatsapp_message, payload)
        return {"status": "received"}
    except Exception as e:
        print("Erro ao parsear webhook payload:", e)
        # Devolvemos 200 pra Evolution não ficar tentando reenviar mensagem mal formatada
        return {"status": "error", "detail": "bad request"}
