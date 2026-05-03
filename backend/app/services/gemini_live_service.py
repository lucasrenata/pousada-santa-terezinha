import os
import asyncio
import json
import logging
import base64
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class GeminiLiveService:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(
            api_key=self.api_key, 
            http_options={'api_version': 'v1alpha'}
        )
        self.model_name = "gemini-2.5-flash-native-audio-preview-12-2025"

    def _get_tool_declarations(self):
        """Retorna as declarações de ferramentas formatadas para o novo SDK."""
        return [
            types.FunctionDeclaration(
                name="robot_inventory_viewer",
                description="Consulta o estoque atual de produtos no hotel.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "category": types.Schema(type="STRING", description="Categoria opcional (ex: bebidas, limpeza).")
                    }
                )
            ),
            types.FunctionDeclaration(
                name="robot_room_viewer",
                description="Verifica o status dos quartos (limpeza, ocupação, manutenção).",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "status": types.Schema(type="STRING", description="Status opcional para filtrar.")
                    }
                )
            ),
            types.FunctionDeclaration(
                name="robot_room_status_manager",
                description="Altera o status de um quarto (ex: colocar em limpeza ou manutenção).",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "room_id": types.Schema(type="STRING", description="Número/ID do quarto."),
                        "new_status": types.Schema(type="STRING", description="Novo status: 'disponivel', 'limpeza' ou 'manutencao'."),
                        "note": types.Schema(type="STRING", description="Observação opcional.")
                    },
                    required=["room_id", "new_status"]
                )
            ),
            types.FunctionDeclaration(
                name="robot_mark_room_as_ready",
                description="Marca um quarto como limpo e pronto para uso (status disponivel).",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "room_id": types.Schema(type="STRING", description="Número/ID do quarto.")
                    },
                    required=["room_id"]
                )
            ),
            types.FunctionDeclaration(
                name="robot_cashier_history_viewer",
                description="Consulta o histórico de fechamentos de caixa (sessões), incluindo operador, valores e horários.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "date_str": types.Schema(type="STRING", description="Data específica no formato YYYY-MM-DD para filtrar os caixas.")
                    }
                )
            ),
            types.FunctionDeclaration(
                name="robot_pdf_reporter",
                description="Gera relatórios PDF analíticos (financeiro, estoque ou compras).",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "report_type": types.Schema(type="STRING", description="Tipo do relatório: 'finance', 'inventory' ou 'shopping'."),
                        "mode": types.Schema(type="STRING", description="Para financeiro: 'full' ou 'summary'.")
                    },
                    required=["report_type"]
                )
            ),
            types.FunctionDeclaration(
                name="robot_expense_launcher",
                description="Lança uma despesa operacional ou conta a pagar.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "description": types.Schema(type="STRING", description="Descrição da despesa."),
                        "amount": types.Schema(type="NUMBER", description="Valor em reais."),
                        "category": types.Schema(type="STRING", description="Categoria (agua, energia, salarios, etc).")
                    },
                    required=["description", "amount"]
                )
            ),
            types.FunctionDeclaration(
                name="robot_get_analytics_data",
                description="Retorna dados crus de faturamento, ocupação e financeiro para análise interpretativa.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "start_date": types.Schema(type="STRING", description="Data inicial (YYYY-MM-DD)."),
                        "end_date": types.Schema(type="STRING", description="Data final (YYYY-MM-DD).")
                    }
                )
            ),
            types.FunctionDeclaration(
                name="robot_open_cashiers_viewer",
                description="Lista quais caixas (PDV) estão abertos hoje e quem são os operadores.",
                parameters=types.Schema(type="OBJECT", properties={})
            ),
            types.FunctionDeclaration(
                name="robot_active_guests_viewer",
                description="Lista todos os hóspedes que estão atualmente hospedados.",
                parameters=types.Schema(type="OBJECT", properties={})
            )
        ]

    async def _handle_tool_call(self, tool_call, tenant_id, client_websocket):
        from agents.admin_agent import (
            inventory_viewer_logic, room_viewer_logic, pdf_generator_logic, 
            expense_logic, pdv_session_logic, active_guests_logic,
            room_status_logic, robot_cashier_history_viewer
        )
        from agents.shared_tools import get_raw_analytics_logic

        name = tool_call.name
        args = tool_call.args
        
        logger.info(f"🛠️ Executando {name} para tenant {tenant_id} com args {args}")
        result = {"error": "Falha na execução"}
        
        # Normalização defensiva de argumentos (ex: tirar acentos de status)
        if "status" in args and isinstance(args["status"], str):
            status_map = {
                "disponível": "disponivel",
                "manutenção": "manutencao",
                "ocupado": "ocupado",
                "limpeza": "limpeza"
            }
            norm_status = args["status"].lower().strip()
            args["status"] = status_map.get(norm_status, norm_status)

        try:
            if name == "robot_inventory_viewer":
                result = inventory_viewer_logic(tenant_id, **args)
            elif name == "robot_room_viewer":
                result = room_viewer_logic(tenant_id, **args)
            elif name == "robot_room_status_manager":
                result = room_status_logic(tenant_id, **args)
            elif name == "robot_mark_room_as_ready":
                result = room_status_logic(tenant_id, room_id=args.get("room_id"), new_status="disponivel")
            elif name == "robot_cashier_history_viewer":
                result = robot_cashier_history_viewer(tenant_id=tenant_id, date_str=args.get("date_str"))
            
            elif name == "robot_pdf_reporter":
                result = pdf_generator_logic(tenant_id, **args)
                if "url" in result:
                    await client_websocket.send_json({
                        "server_content": { "model_turn": { "parts": [{"text": f"📄 Relatório Gerado: [{result['title']}]({result['url']})"}] } }
                    })
            elif name == "robot_expense_launcher":
                result = expense_logic(tenant_id, **args)
            elif name == "robot_get_analytics_data":
                result = get_raw_analytics_logic(tenant_id, **args)
            elif name == "robot_open_cashiers_viewer":
                result = pdv_session_logic(tenant_id)
            elif name == "robot_active_guests_viewer":
                result = active_guests_logic(tenant_id)
        except Exception as e:
            logger.error(f"Erro na ferramenta {name}: {e}")
            result = {"error": str(e)}
        return result

    def _sanitize_result(self, result):
        """Converte objetos complexos (SQLAlchemy, datetime) em tipos serializáveis."""
        if isinstance(result, list):
            return [self._sanitize_result(i) for i in result]
        if isinstance(result, dict):
            return {k: self._sanitize_result(v) for k, v in result.items()}
        if hasattr(result, "model_dump"): # Pydantic
            return result.model_dump()
        if hasattr(result, "__dict__"): # SQLAlchemy ou classes simples
            return {k: self._sanitize_result(v) for k, v in result.__dict__.items() if not k.startswith("_")}
        return result

    async def _safe_send_tool_responses(self, session, responses):
        """Envia respostas de ferramentas com tratamento de erro local."""
        try:
            # Sanitização profunda antes de enviar
            sanitized_responses = []
            for resp in responses:
                sanitized_responses.append({
                    "name": resp["name"],
                    "id": resp["id"],
                    "response": {"result": self._sanitize_result(resp["response"]["result"])}
                })
            
            logger.debug(f"📤 Enviando Tool Responses: {sanitized_responses}")
            await session.send(input={"function_responses": sanitized_responses})
            logger.info("✅ Resposta da ferramenta enviada com sucesso")
        except Exception as e:
            logger.error(f"❌ Falha ao enviar resposta da ferramenta: {e}")

    async def connect_and_proxy(self, client_websocket, tenant_id: int):
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part(text="Você é a Ana, assistente holográfica do hotel. Use as ferramentas para ajudar nas tarefas administrativas. IMPORTANTE: Ao gerar relatórios ou links, apenas confirme que o documento está pronto e disponível na tela. NUNCA leia URLs, endereços web ou caminhos de arquivos em voz alta.")]
            ),
            tools=[types.Tool(function_declarations=self._get_tool_declarations())]
        )

        try:
            async with self.client.aio.live.connect(model=self.model_name, config=config) as session:
                logger.info(f"✅ Conexão Live SDK Estabelecida para tenant {tenant_id}")

                session_active = True
                async def send_loop():
                    nonlocal session_active
                    logger.info("🟢 send_loop iniciado")
                    try:
                        while session_active:
                            message = await client_websocket.receive()
                            if message["type"] == "websocket.disconnect":
                                logger.info("🔌 send_loop: Cliente desconectou.")
                                session_active = False
                                break
                            
                            if "text" in message:
                                try:
                                    data = json.loads(message["text"])
                                    if data.get("type") == "audio" and data.get("data"):
                                        audio_bytes = base64.b64decode(data["data"])
                                        await session.send(input={"data": audio_bytes, "mime_type": "audio/pcm;rate=16000"}, end_of_turn=False)
                                    elif data.get("type") == "text" and data.get("data"):
                                        await session.send(input=data["data"], end_of_turn=True)
                                except json.JSONDecodeError:
                                    await session.send(input=message["text"], end_of_turn=True)
                            elif "bytes" in message:
                                await session.send(input={"data": message["bytes"], "mime_type": "audio/pcm;rate=16000"}, end_of_turn=False)
                    except Exception as e:
                        logger.error(f"❌ send_loop erro: {e}")
                    finally:
                        logger.info("🔴 send_loop finalizado")

                async def receive_loop():
                    nonlocal session_active
                    logger.info("🟢 receive_loop iniciado")
                    try:
                        while session_active:
                            try:
                                async for response in session.receive():
                                    if not response:
                                        continue
                                        
                                    logger.debug(f"📥 Mensagem recebida do Gemini")
                                    data = response.model_dump()
                                    
                                    # 1. Processar Conteúdo (Áudio/Texto)
                                    server_content = data.get("server_content")
                                    if server_content:
                                        model_turn = server_content.get("model_turn")
                                        if model_turn:
                                            parts = model_turn.get("parts", [])
                                            for part in parts:
                                                inline_data = part.get("inline_data")
                                                if inline_data and isinstance(inline_data.get("data"), bytes):
                                                    audio_bytes = inline_data["data"]
                                                    inline_data["data"] = base64.b64encode(audio_bytes).decode('utf-8')
                                        
                                        await client_websocket.send_json(data)
                                    
                                    # 2. Processar Ferramentas
                                    if response.tool_call:
                                        logger.info(f"🔧 Processando Tool Call...")
                                        if not server_content:
                                            await client_websocket.send_json(data)
                                            
                                        tool_responses = []
                                        for fc in response.tool_call.function_calls:
                                            res = await self._handle_tool_call(fc, tenant_id, client_websocket)
                                            sanitized_res = self._sanitize_result(res)
                                            
                                            # Debug especial para URL
                                            if isinstance(sanitized_res, dict) and "url" in sanitized_res:
                                                logger.info(f"🔗 URL Gerada: {sanitized_res['url']}")

                                            tool_responses.append({
                                                "name": fc.name,
                                                "id": fc.id,
                                                "response": {"result": sanitized_res}
                                            })
                                        
                                        if tool_responses:
                                            logger.info(f"📤 Enviando respostas ({len(tool_responses)})")
                                            await session.send(input={"function_responses": tool_responses})
                                            logger.info("✅ Respostas enviadas com sucesso.")
                                
                                # Se o async for terminar normalmente, damos um pequeno break e tentamos de novo
                                # a menos que a sessão tenha sido fechada
                                await asyncio.sleep(0.1)
                                if not session_active: break

                            except Exception as e:
                                if "closed" in str(e).lower() or "1000" in str(e) or "1006" in str(e):
                                    session_active = False
                                    break
                                logger.warning(f"⚠️ Erro no stream receive: {e}")
                                await asyncio.sleep(1)

                    except Exception as e:
                        logger.warning(f"⚠️ receive_loop fatal error: {e}", exc_info=True)
                    finally:
                        session_active = False
                        logger.info("🔴 receive_loop finalizado")

                # Executa ambos e para assim que o primeiro terminar
                done, pending = await asyncio.wait(
                    [asyncio.create_task(send_loop()), asyncio.create_task(receive_loop())],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                logger.info(f"🏁 Sessão finalizada. Tarefa que completou primeiro: {done}")
                for task in pending:
                    task.cancel()

        except Exception as e:
            logger.error(f"Falha crítica na sessão Live: {e}")
            raise

gemini_live_service = GeminiLiveService()
