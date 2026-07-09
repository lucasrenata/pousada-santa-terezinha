import os
import asyncio
import json
import logging
import base64
import re
from google import genai
from google.genai import types

from agents.supervisor_agent import SupervisorAgent
from database import SessionLocal, set_tenant_context
import models

logger = logging.getLogger(__name__)

class CustomerLiveService:
    """
    Serviço Gemini Live que atua como interface de VOZ para o SupervisorAgent.
    Respeita a arquitetura de especialistas (Reservas, Pagamento, FAQ).
    """
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(
            api_key=self.api_key, 
            http_options={'api_version': 'v1alpha'}
        )
        self.model_name = "gemini-2.5-flash-native-audio-preview-12-2025" 

    async def _get_dynamic_settings(self, tenant_id: int):
        """Busca as configurações de personalidade da IA no banco de dados."""
        db = SessionLocal()
        try:
            set_tenant_context(db, tenant_id)
            keys = ['ai_receptionist_name', 'ai_personality', 'ai_greeting', 'pousada_name']
            settings = db.query(models.SystemSetting).filter(models.SystemSetting.key.in_(keys)).all()
            config_map = {s.key: s.value for s in settings}
            return {
                "name": config_map.get('ai_receptionist_name', 'Ana'),
                "personality": config_map.get('ai_personality', 'gentil, prestativa e profissional'),
                "greeting": config_map.get('ai_greeting', 'Olá! Como posso ajudar você hoje?'),
                "pousada": config_map.get('pousada_name', 'Nossa Pousada')
            }
        finally:
            db.close()

    def _get_tool_declarations(self):
        """Define o Supervisor como a única ferramenta de decisão para a IA de voz."""
        return [
            types.FunctionDeclaration(
                name="consultar_supervisor",
                description="Consulte o supervisor para qualquer assunto sobre reservas, preços, pagamentos, CPF, cadastro ou dúvidas da pousada. Use sempre que o usuário fizer uma solicitação ou pergunta.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "mensagem": types.Schema(type="STRING", description="O que o hóspede disse ou perguntou.")
                    },
                    required=["mensagem"]
                )
            )
        ]

    async def connect_and_proxy(self, tenant_id: int, session_id: str, client_websocket):
        """Estabelece a ponte entre o Voz/Chat e o SupervisorAgent (Cérebro)."""
        supervisor = SupervisorAgent(tenant_id)
        ai_config = await self._get_dynamic_settings(tenant_id)
        
        personality_prompt = """Você é a ANA, a Recepcionista de Elite da Pousada Santa Terezinha. Sua missão é seguir rigorosamente o ROTEIRO OFICIAL para garantir uma reserva perfeita.

### 📋 ROTEIRO OFICIAL DE ATENDIMENTO (SIGA ESTA ORDEM):
1. **BOAS VINDAS**: Saudação inicial acolhedora.
2. **DATAS**: Perguntar as datas de entrada e saída.
3. **PÚBLICO**: Perguntar quantas pessoas e as idades (importante para o valor).
4. **COTAÇÃO**: Fazer a consulta e entregar os valores da reserva.
5. **REVISÃO**: Confirmar os quartos e valores com o hóspede.
6. **INTENÇÃO**: Se o hóspede der o OK, pedir o CPF do responsável.
7. **CADASTRO**: Consultar o CPF. Se não houver cadastro, fornecer o LINK DE CADASTRO e solicitar o preenchimento.
8. **RECEPÇÃO PERSONALIZADA**: Ao receber o cadastro, agradecer usando o NOME do hóspede.
9. **CONFIRMAÇÃO FINAL**: Confirmar todos os dados: Quarto, Valor total e Quantidade de pessoas.
10. **EFETIVAÇÃO**: O hóspede confirmando, gerar a reserva no sistema.
11. **SUCESSO**: Informar que a reserva foi criada e explicar o procedimento de pagamento do sinal.
12. **COBRANÇA**: O hóspede dando o OK, entregar o Link de Pagamento ou Chave PIX.
13. **COMPROVANTE**: Solicitar o envio do comprovante para confirmação da equipe.
14. **ENCERRAMENTO**: Agradecer e se colocar à disposição.

### ⚠️ REGRAS CRÍTICAS:
- **MEMÓRIA DO QUADRO**: Use os 'FATOS COLETADOS' injetados pelo sistema para nunca repetir uma pergunta. Se o nome já apareceu no cadastro, use-o imediatamente.
- **NUNCA PULE ETAPAS**: Siga a ordem numérica. Se o hóspede quiser pular para o preço, peça as datas e pessoas primeiro.
- **LINK DE CADASTRO**: Se o sistema informar que o CPF não existe, você deve falar: "Não encontrei seu cadastro. Por favor, preencha Rapidamente neste link para prosseguirmos: [LINK]".
- **TOM DE VOZ**: Profissional, vendedora e extremamente educada.
"""

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part(text=personality_prompt)]
            ),
            tools=[types.Tool(function_declarations=self._get_tool_declarations())]
        )

        try:
            async with self.client.aio.live.connect(model=self.model_name, config=config) as session:
                logger.info(f"✅ Conexão Live/Supervisor (Tool-Mode) estabelecida para tenant {tenant_id}")

                session_active = True

                async def send_loop():
                    nonlocal session_active
                    try:
                        while session_active:
                            message = await client_websocket.receive()
                            if message["type"] == "websocket.disconnect":
                                session_active = False
                                break
                            
                            if "text" in message:
                                try:
                                    data = json.loads(message["text"])
                                    if data.get("type") == "audio" and data.get("data"):
                                        audio_bytes = base64.b64decode(data["data"])
                                        await session.send(input={"data": audio_bytes, "mime_type": "audio/pcm;rate=16000"}, end_of_turn=False)
                                    elif data.get("type") == "text" and data.get("data"):
                                        user_text = data["data"]
                                        logger.info(f"📩 Hóspede (Texto): {user_text}")
                                        
                                        result = await supervisor.process(user_text, session_id)
                                        ai_response = result.get("response", "")
                                        
                                        await client_websocket.send_json({
                                            "server_content": {"model_turn": {"parts": [{"text": ai_response}]}}
                                        })
                                        await session.send(input=ai_response, end_of_turn=True)
                                        
                                except json.JSONDecodeError:
                                    pass
                            elif "bytes" in message:
                                await session.send(input={"data": message["bytes"], "mime_type": "audio/pcm;rate=16000"}, end_of_turn=False)
                    except Exception as e:
                        logger.error(f"❌ send_loop atendente fatal: {e}")
                    finally:
                        session_active = False

                async def receive_loop():
                    nonlocal session_active
                    try:
                        while session_active:
                            try:
                                async for response in session.receive():
                                    if not response: continue
                                    
                                    data = response.model_dump()
                                    
                                    # 1. Processa Áudio da Ana
                                    server_content = data.get("server_content")
                                    if server_content:
                                        model_turn = server_content.get("model_turn")
                                        if model_turn:
                                            for part in model_turn.get("parts", []):
                                                inline_data = part.get("inline_data")
                                                if inline_data and isinstance(inline_data.get("data"), bytes):
                                                    inline_data["data"] = base64.b64encode(inline_data["data"]).decode("utf-8")
                                        await client_websocket.send_json(data)

                                    # 2. Processa Chamada do Supervisor (FERRAMENTA)
                                    if response.tool_call:
                                        tool_responses = []
                                        for fc in response.tool_call.function_calls:
                                            if fc.name == "consultar_supervisor":
                                                user_msg = fc.args.get("mensagem", "")
                                                logger.info(f"🧠 Consultando Supervisor via Voz: {user_msg}")
                                                
                                                result = await supervisor.process(user_msg, session_id)
                                                ai_resp = result.get("response", "Entendido, um momento.")
                                                
                                                # Envia texto para o chat também
                                                await client_websocket.send_json({
                                                    "server_content": {"model_turn": {"parts": [{"text": ai_resp}]}}
                                                })

                                                tool_responses.append({
                                                    "name": fc.name,
                                                    "id": fc.id,
                                                    "response": {"status": "Sincronizado"}
                                                })
                                                
                                                # DIRETRIZ: Passa a verdade do sistema e os FATOS para a IA de voz
                                                facts = result.get("facts", {})
                                                directive = f"FATOS COLETADOS PELO SISTEMA: {json.dumps(facts, ensure_ascii=False)}\nDIRETRIZ DE FALA: {ai_resp}"
                                                logger.info(f"📤 Injetando Contexto na Ana: {directive[:100]}...")
                                                await session.send(input=directive, end_of_turn=True)
                                        
                                        if tool_responses:
                                            await session.send(input={"function_responses": tool_responses})

                                await asyncio.sleep(0.1)
                                if not session_active: break
                            except Exception as e:
                                if "closed" in str(e).lower():
                                    session_active = False
                                    break
                                logger.warning(f"⚠️ receive_loop erro: {e}")
                                await asyncio.sleep(1)
                    except Exception as e:
                        logger.warning(f"⚠️ receive_loop fatal: {e}")
                    finally:
                        session_active = False

                done, pending = await asyncio.wait(
                    [asyncio.create_task(send_loop()), asyncio.create_task(receive_loop())],
                    return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending: task.cancel()

        except Exception as e:
            logger.error(f"Falha crítica no atendente Live (tenant {tenant_id}): {e}")
            raise

gemini_live_service = CustomerLiveService()
