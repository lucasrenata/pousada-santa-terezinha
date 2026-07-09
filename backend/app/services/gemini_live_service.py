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
        self.active_sessions = {} # {tenant_id: session_object}

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
                name="robot_dynamic_pdf_composer",
                description="Compositor de Documentos Dinâmicos: Gera um PDF profissional com o cabeçalho oficial do hotel (Nome/CNPJ). Use para relatórios específicos e objetivos pedidos pelo usuário.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "title": types.Schema(type="STRING", description="Título do documento (ex: 'Relatório de Consumo Quarto 101')"),
                        "sections": types.Schema(
                            type="ARRAY", 
                            description="Lista de seções do documento (tabelas, textos, kpis).",
                            items=types.Schema(type="OBJECT")
                        )
                    },
                    required=["title", "sections"]
                )
            ),
            types.FunctionDeclaration(
                name="robot_active_guests_viewer",
                description="Lista todos os hóspedes que estão atualmente hospedados.",
                parameters=types.Schema(type="OBJECT", properties={})
            ),
            types.FunctionDeclaration(
                name="robot_room_occupancy_details",
                description="Retorna detalhes completos de uma ocupação ativa em um quarto (extrato, check-in/out, saldo).",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "room_id": types.Schema(type="STRING", description="Número do quarto (ex: '101').")
                    },
                    required=["room_id"]
                )
            ),
            # ── NOVAS FERRAMENTAS (MULTI-AGENTE) ──────────────────────────────────
            types.FunctionDeclaration(
                name="robot_booking_summary",
                description="Panorama das reservas da pousada. Mostra quantas reservas existem por status (pendente, confirmado, ativo, concluido, cancelado). Use para responder 'quantas reservas temos?' ou 'check-ins de hoje'.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "status": types.Schema(type="STRING", description="Filtrar por status específico: 'pendente', 'confirmado', 'ativo', 'concluido' ou 'cancelado'."),
                        "check_in_today": types.Schema(type="BOOLEAN", description="Se true, lista apenas check-ins previstos para hoje.")
                    }
                )
            ),
            types.FunctionDeclaration(
                name="robot_consumption_launcher",
                description="Lança itens de consumo (bebidas, serviços, lanches) na conta de um quarto com check-in ativo. Deduz automaticamente do estoque.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "room_id": types.Schema(type="STRING", description="Número do quarto."),
                        "product_name": types.Schema(type="STRING", description="Nome do produto/item a lançar."),
                        "quantity": types.Schema(type="INTEGER", description="Quantidade (padrão: 1).")
                    },
                    required=["room_id", "product_name"]
                )
            ),
            types.FunctionDeclaration(
                name="robot_checkout_manager",
                description="Gerencia o checkout de um quarto. Primeiro faça confirm=false para ver o extrato antes de fechar.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "room_id": types.Schema(type="STRING", description="Número do quarto."),
                        "confirm": types.Schema(type="BOOLEAN", description="False para prévia, True para confirmar o checkout."),
                        "payment_method": types.Schema(type="STRING", description="Método de pagamento: pix, credito, debito, dinheiro.")
                    },
                    required=["room_id"]
                )
            ),
            types.FunctionDeclaration(
                name="robot_find_booking",
                description="Localiza reservas por CPF do hóspede, nome, número do quarto ou ID direto.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "cpf": types.Schema(type="STRING", description="CPF do hóspede."),
                        "name": types.Schema(type="STRING", description="Nome parcial do hóspede."),
                        "room_id": types.Schema(type="STRING", description="Número do quarto."),
                        "booking_id": types.Schema(type="INTEGER", description="ID direto da reserva.")
                    }
                )
            ),
            types.FunctionDeclaration(
                name="robot_confirm_payment",
                description="Confirma pagamento de uma reserva manualmente e registra a receita.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "booking_id": types.Schema(type="INTEGER", description="ID da reserva."),
                        "method": types.Schema(type="STRING", description="Método: pix, credito, debito, dinheiro.")
                    },
                    required=["booking_id"]
                )
            ),
        ]

    async def _handle_tool_call(self, tool_call, tenant_id, client_websocket):
        from agents.admin_agent import (
            inventory_viewer_logic, room_viewer_logic, pdf_generator_logic, 
            expense_logic, pdv_session_logic, active_guests_logic,
            room_status_logic, robot_cashier_history_viewer, robot_dynamic_pdf_composer,
            room_occupancy_details_logic, consumption_logic, checkout_logic,
            booking_summary_logic
        )
        from agents.shared_tools import (
            get_raw_analytics_logic, find_booking_logic, confirm_payment_logic
        )

        name = tool_call.name
        args = tool_call.args
        
        logger.info(f"🛠️ Executando {name} para tenant {tenant_id} com args {args}")
        result = {"error": "Falha na execução"}
        
        # Normalização defensiva de argumentos
        if "status" in args and isinstance(args["status"], str):
            status_map = {
                "disponível": "disponivel",
                "manutenção": "manutencao",
                "ocupado": "ocupado",
                "limpeza": "limpeza"
            }
            norm_status = args["status"].lower().strip()
            args["status"] = status_map.get(norm_status, norm_status)

        # ── HELPER: Anuncia ao usuário antes de tarefas longas ───────────────
        async def announce(msg: str):
            """Envia mensagem humanizada antes de executar tarefas demoradas."""
            await client_websocket.send_json({
                "server_content": {"model_turn": {"parts": [{"text": msg}]}}
            })

        try:
            if name == "robot_inventory_viewer":
                result = inventory_viewer_logic(tenant_id, **args)
                if isinstance(result.get("items"), list) and len(result["items"]) > 0:
                    md = "### 📦 Status do Estoque\n"
                    md += "| Produto | Qtd Atual | Mínimo | Status |\n| :--- | :--- | :--- | :--- |\n"
                    for p in result["items"]:
                        status = "✅ OK" if p['stock'] >= p['min_stock'] else "⚠️ BAIXO"
                        md += f"| {p['name']} | {p['stock']} | {p['min']} | {status} |\n"
                    await client_websocket.send_json({"server_content": {"model_turn": {"parts": [{"text": md}]}}})

            elif name == "robot_room_viewer":
                result = room_viewer_logic(tenant_id, **args)

            elif name == "robot_room_status_manager":
                result = room_status_logic(tenant_id, **args)

            elif name == "robot_mark_room_as_ready":
                result = room_status_logic(tenant_id, room_id=args.get("room_id"), new_status="disponivel")

            elif name == "robot_cashier_history_viewer":
                result = robot_cashier_history_viewer(tenant_id=tenant_id, date_str=args.get("date_str"))
                if "sessions" in result:
                    md = "### 🏦 Histórico de Caixas\n"
                    md += "| ID | Operador | Abertura | Fechamento | Status |\n| :--- | :--- | :--- | :--- | :--- |\n"
                    for s in result['sessions']:
                        md += f"| {s['id']} | {s['operador']} | {s['valor_abertura']} | {s['valor_fechamento']} | {s['status']} |\n"
                    await client_websocket.send_json({"server_content": {"model_turn": {"parts": [{"text": md}]}}})
            
            elif name == "robot_room_occupancy_details":
                result = room_occupancy_details_logic(tenant_id=tenant_id, room_id=args.get("room_id"))
                if "quarto" in result:
                    md = f"### 📑 Extrato Quarto {result['quarto']}\n"
                    md += f"**Hóspede:** {result['hospede_principal']}\n"
                    md += f"**Período:** {result['check_in']} até {result['check_out_previsto']}\n\n"
                    if result['consumos']:
                        md += "| Item | Qtd | Preço | Subtotal |\n| :--- | :--- | :--- | :--- |\n"
                        for c in result['consumos']:
                            md += f"| {c['item']} | {c['quantidade']} | {c['preco_unitario']} | {c['subtotal']} |\n"
                    resumo = result['resumo_financeiro']
                    md += f"\n**💰 TOTAL PARCIAL: {resumo['valor_total_parcial']}**"
                    await client_websocket.send_json({"server_content": {"model_turn": {"parts": [{"text": md}]}}})

            # ── NOVAS FERRAMENTAS ─────────────────────────────────────────────

            elif name == "robot_booking_summary":
                result = booking_summary_logic(
                    tenant_id,
                    status=args.get("status"),
                    check_in_today=args.get("check_in_today", False)
                )
                # Formata panorama em tabela legível
                if "resumo_por_status" in result:
                    md = "### 📊 Panorama de Reservas\n"
                    md += "| Status | Quantidade |\n| :--- | :--- |\n"
                    for s, count in result["resumo_por_status"].items():
                        md += f"| {s.capitalize()} | {count} |\n"
                    md += f"\n**Total: {result['total']} reservas**"
                    await client_websocket.send_json({"server_content": {"model_turn": {"parts": [{"text": md}]}}})
                elif "reservas" in result:
                    reservas = result["reservas"]
                    md = f"### 📊 Reservas ({result.get('status_filtrado', 'Hoje').capitalize()}): {len(reservas)}\n"
                    if reservas:
                        md += "| ID | Hóspede | Quarto | Check-in |\n| :--- | :--- | :--- | :--- |\n"
                        for b in reservas[:10]:
                            md += f"| #{b['id']} | {b['hospede']} | {b['quarto']} | {b.get('check_in', '')} |\n"
                    await client_websocket.send_json({"server_content": {"model_turn": {"parts": [{"text": md}]}}})

            elif name == "robot_consumption_launcher":
                result = consumption_logic(
                    tenant_id,
                    room_id=args.get("room_id"),
                    product_name=args.get("product_name"),
                    quantity=args.get("quantity", 1)
                )

            elif name == "robot_checkout_manager":
                confirm = args.get("confirm", False)
                action = "confirm" if confirm else "preview"
                result = checkout_logic(
                    tenant_id,
                    room_id=args.get("room_id"),
                    action=action,
                    payment_method=args.get("payment_method", "pix")
                )

            elif name == "robot_find_booking":
                result = find_booking_logic(
                    tenant_id,
                    cpf=args.get("cpf", ""),
                    name=args.get("name", ""),
                    room_id=args.get("room_id", ""),
                    booking_id=args.get("booking_id")
                )

            elif name == "robot_confirm_payment":
                result = confirm_payment_logic(
                    tenant_id,
                    booking_id=args.get("booking_id"),
                    method=args.get("method", "pix")
                )

            # ── FERRAMENTAS COM FEEDBACK HUMANIZADO (TAREFAS LONGAS) ──────────

            elif name == "robot_dynamic_pdf_composer":
                await announce("📄 Estou compondo o documento personalizado, um momento...")
                result = robot_dynamic_pdf_composer(tenant_id, title=args.get("title"), sections=args.get("sections"))
                if "url" in result:
                    await client_websocket.send_json({
                        "server_content": {"model_turn": {"parts": [{"text": f"📄 Documento Gerado: [{result['title']}]({result['url']})"}]}}
                    })

            elif name == "robot_pdf_reporter":
                report_labels = {"finance": "financeiro", "inventory": "de estoque", "shopping": "de compras"}
                label = report_labels.get(args.get("report_type", ""), "")
                await announce(f"📄 Estou gerando o relatório {label} agora, um momento...")
                result = pdf_generator_logic(tenant_id, **args)
                if "url" in result:
                    await client_websocket.send_json({
                        "server_content": {"model_turn": {"parts": [{"text": f"📄 Relatório Gerado: [{result['title']}]({result['url']})"}]}}
                    })

            elif name == "robot_expense_launcher":
                result = expense_logic(tenant_id, **args)

            elif name == "robot_get_analytics_data":
                await announce("📊 Buscando os dados de análise, um momento...")
                result = get_raw_analytics_logic(tenant_id, **args)

            elif name == "robot_open_cashiers_viewer":
                result = pdv_session_logic(tenant_id)

            elif name == "robot_active_guests_viewer":
                result = active_guests_logic(tenant_id)
                if isinstance(result.get("guests"), list):
                    md = "### 👤 Hóspedes Ativos\n"
                    md += "| Quarto | Hóspede | Check-in |\n| :--- | :--- | :--- |\n"
                    for g in result["guests"]:
                        md += f"| {g['quarto']} | {g['nome']} | {g['check_in']} |\n"
                    await client_websocket.send_json({"server_content": {"model_turn": {"parts": [{"text": md}]}}})

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
        # --- PREVENÇÃO DE VOZES DUPLICADAS (SINGLETON POR TENANT) ---
        if tenant_id in self.active_sessions:
            logger.warning(f"⚠️ [LIVE] Sessão duplicada detectada para tenant {tenant_id}. Encerrando anterior...")
            old_session = self.active_sessions[tenant_id]
            old_session['active'] = False
            await asyncio.sleep(0.3) # Tempo para a sessão antiga fechar

        session_state = {"active": True}
        self.active_sessions[tenant_id] = session_state

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part(text="Você é a Ana, assistente holográfica do hotel. Use as ferramentas para ajudar nas tarefas administrativas. IMPORTANTE: Ao gerar relatórios ou links, apenas confirme que o documento está pronto e disponível na tela. NUNCA leia URLs ou caminhos de arquivos em voz alta.")]
            ),
            tools=[types.Tool(function_declarations=self._get_tool_declarations())]
        )

        try:
            async with self.client.aio.live.connect(model=self.model_name, config=config) as session:
                logger.info(f"✅ Conexão Live SDK Estabelecida para tenant {tenant_id}")

                async def send_loop():
                    logger.info(f"🟢 [TENANT {tenant_id}] send_loop iniciado")
                    try:
                        while session_state['active']:
                            message = await client_websocket.receive()
                            if message["type"] == "websocket.disconnect":
                                logger.info(f"🔌 [TENANT {tenant_id}] Cliente desconectou.")
                                session_state['active'] = False
                                break
                            
                            if not session_state['active']: break

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
                        if session_state['active']:
                            logger.error(f"❌ [TENANT {tenant_id}] send_loop erro: {e}")
                    finally:
                        logger.info(f"🔴 [TENANT {tenant_id}] send_loop finalizado")

                async def receive_loop():
                    logger.info(f"🟢 [TENANT {tenant_id}] receive_loop iniciado")
                    try:
                        while session_state['active']:
                            try:
                                async for response in session.receive():
                                    if not session_state['active']: break
                                    
                                    if not response: continue
                                        
                                    logger.debug(f"📥 [TENANT {tenant_id}] Mensagem recebida")
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
                                        logger.info(f"🔧 [TENANT {tenant_id}] Processando Tool Call...")
                                        if not server_content:
                                            await client_websocket.send_json(data)
                                            
                                        tool_responses = []
                                        for fc in response.tool_call.function_calls:
                                            res = await self._handle_tool_call(fc, tenant_id, client_websocket)
                                            sanitized_res = self._sanitize_result(res)
                                            
                                            tool_responses.append({
                                                "name": fc.name,
                                                "id": fc.id,
                                                "response": {"result": sanitized_res}
                                            })
                                        
                                        if tool_responses:
                                            logger.info(f"📤 [TENANT {tenant_id}] Enviando respostas ({len(tool_responses)})")
                                            await session.send(input={"function_responses": tool_responses})
                                
                                await asyncio.sleep(0.1)
                                if not session_state['active']: break

                            except Exception as e:
                                if "closed" in str(e).lower() or "1000" in str(e) or "1006" in str(e):
                                    session_state['active'] = False
                                    break
                                logger.warning(f"⚠️ [TENANT {tenant_id}] Erro no stream receive: {e}")
                                await asyncio.sleep(1)

                    except Exception as e:
                        if session_state['active']:
                            logger.warning(f"⚠️ [TENANT {tenant_id}] receive_loop fatal: {e}")
                    finally:
                        session_state['active'] = False
                        logger.info(f"🔴 [TENANT {tenant_id}] receive_loop finalizado")

                # Executa ambos em paralelo
                await asyncio.wait(
                    [asyncio.create_task(send_loop()), asyncio.create_task(receive_loop())],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                logger.info(f"🏁 [TENANT {tenant_id}] Sessão Live finalizada.")

        except Exception as e:
            logger.error(f"❌ [TENANT {tenant_id}] Falha crítica na sessão Live: {e}")
        finally:
            session_state['active'] = False
            if tenant_id in self.active_sessions and self.active_sessions[tenant_id] == session_state:
                del self.active_sessions[tenant_id]
                logger.info(f"🧹 [TENANT {tenant_id}] Cache de sessão limpo.")

gemini_live_service = GeminiLiveService()
