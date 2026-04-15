import json
import os
from sqlalchemy.orm import Session
import models
from database import SessionLocal, set_tenant_context
from utils.finance_pdf import generate_financial_report
from utils.inventory_pdf import generate_inventory_report, generate_shopping_list_report
from datetime import datetime, date, timedelta
from typing import Optional, List

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode
from agents import shared_tools

# =============================================================================
# CONVERSÃO DE HISTÓRICO
# =============================================================================
def convert_history_to_langchain(history: list):
    """Converte o histórico do DB para o formato LangChain."""
    lc_messages = []
    for h in history[-15:]:
        role = h.get("role")
        content = h.get("content", "")
        # No futuro, se salvarmos tool_calls no DB, recuperamos aqui
        tool_calls = h.get("tool_calls")
        if role == "user": lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            if tool_calls: lc_messages.append(AIMessage(content=content, tool_calls=tool_calls))
            else: lc_messages.append(AIMessage(content=content))
        elif role == "tool": lc_messages.append(ToolMessage(content=content, tool_call_id=h.get("tool_call_id", "")))
    return lc_messages

# =============================================================================
# MICRO-ROBÔS: LÓGICAS ESPECIALIZADAS (BACKEND)
# Cada robô agora gerencia sua própria sessão de banco de dados para evitar conflitos concorrentes.
# =============================================================================

# --- GRUPO ESTOQUE ---

def inventory_sync_logic(tenant_id: int, name: str, quantity_change: int = 0, price: float = None, category: str = None, barcode: str = "", cost_price: float = None, markup_percent: float = None) -> dict:
    """Lógica atômica para sincronização (entrada/saída/cadastro) de produtos."""
    if not name: return {"error": "Nome do produto é obrigatório."}
    
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        final_price = price
        if cost_price is not None and markup_percent is not None:
            final_price = round(cost_price * (1 + markup_percent / 100), 2)

        existing = db.query(models.Product).filter(models.Product.name.ilike(f"{name}")).first()
        if not existing:
            existing = db.query(models.Product).filter(models.Product.name.ilike(f"%{name}%")).first()

        if existing:
            old_stock = existing.stock_quantity
            existing.stock_quantity += quantity_change
            if final_price is not None: existing.price = final_price
            if cost_price is not None: existing.cost_price = cost_price
            if markup_percent is not None: existing.markup_percent = markup_percent
            if category: existing.category = category
            if barcode: existing.barcode = barcode
            db.commit()
            return {
                "status": "updated", "product": existing.name, "old_stock": old_stock, 
                "new_stock": existing.stock_quantity, "price": existing.price,
                "message": f"Produto '{existing.name}' atualizado. Estoque: {existing.stock_quantity}."
            }
        else:
            if final_price is None: final_price = 0.0
            new_p = models.Product(
                name=name, price=final_price, category=category or "Diversos", 
                stock_quantity=quantity_change, barcode=barcode or None,
                cost_price=cost_price or 0.0, markup_percent=markup_percent or 0.0
            )
            db.add(new_p)
            db.commit()
            db.refresh(new_p)
            return {"status": "created", "product": new_p.name, "stock": new_p.stock_quantity, "message": f"Novo produto '{new_p.name}' cadastrado."}

def inventory_viewer_logic(tenant_id: int, name: str = "", only_alerts: bool = False) -> dict:
    """Lógica atômica para consulta de níveis de estoque e alertas críticos."""
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        query = db.query(models.Product).filter(models.Product.is_active == True)
        if only_alerts:
            query = query.filter(models.Product.stock_quantity <= models.Product.min_stock)
        elif name:
            query = query.filter(models.Product.name.ilike(f"%{name}%"))
        
        prods = query.all()
        return {
            "count": len(prods),
            "items": [{"name": p.name, "stock": p.stock_quantity, "min": p.min_stock, "price": p.price} for p in prods]
        }

# --- GRUPO OPERAÇÕES ---

def room_status_logic(tenant_id: int, room_id: str, new_status: str, note: str = "") -> dict:
    """Lógica atômica para alteração de estado (limpeza, manutenção, etc) de quartos."""
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        room = db.query(models.Room).filter(models.Room.id == room_id).first()
        if not room: return {"error": f"Quarto {room_id} não existe."}
        
        valid = ["disponivel", "limpeza", "manutencao"]
        status = (new_status or note or "").lower()
        if "liber" in status or "dispon" in status: status = "disponivel"
        elif "limp" in status: status = "limpeza"
        elif "manut" in status: status = "manutencao"
        
        if status not in valid: return {"error": f"Status '{status}' inválido."}
        
        room.status = status
        if status == "manutencao": 
            room.maintenance_note = note or "Manutenção via Agente"
        else:
            room.maintenance_note = None
        db.commit()
        return {"success": True, "room": room_id, "new_status": status}

def room_setup_logic(tenant_id: int, room_id: str, max_capacity: int = 2, price: float = 150.0, description: str = "", floor: int = 1, room_type: str = "Standard") -> dict:
    """Lógica atômica para CADASTRO e CONFIGURAÇÃO FÍSICA de quartos."""
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        room = db.query(models.Room).get(room_id)
        if room:
            room.max_capacity = max_capacity
            room.price_per_night = price
            room.type = room_type
            if description: room.description = description
            room.floor = floor
            db.commit()
            return {"status": "updated", "room": room_id, "message": f"Quarto {room_id} atualizado."}
        else:
            new_room = models.Room(
                id=room_id, type=room_type, max_capacity=max_capacity, 
                price_per_night=price, description=description, 
                floor=floor, status=models.RoomStatus.DISPONIVEL
            )
            db.add(new_room)
            db.commit()
            return {"status": "created", "room": room_id, "message": f"Novo quarto {room_id} cadastrado como {room_type}."}

def consumption_logic(tenant_id: int, room_id: str, product_name: str, quantity: int = 1) -> dict:
    """Lógica atômica para lançamento de consumo em contas de hóspedes."""
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        booking = db.query(models.Booking).filter(models.Booking.room_id == room_id, models.Booking.status == models.BookingStatus.ATIVO).first()
        if not booking: return {"error": f"Sem check-in ativo no quarto {room_id}."}
        
        prod = db.query(models.Product).filter(models.Product.name.ilike(f"%{product_name}%"), models.Product.is_active == True).first()
        if not prod: return {"error": f"Produto '{product_name}' não encontrado."}
        if prod.stock_quantity < quantity: return {"error": f"Estoque insuficiente."}
        
        cons = models.Consumption(booking_id=booking.id, product_id=prod.id, quantity=quantity, unit_price=prod.price)
        prod.stock_quantity -= quantity
        db.add(cons)
        db.commit()
        return {"success": True, "message": f"Lançado {quantity}x {prod.name} no quarto {room_id}."}

def room_viewer_logic(tenant_id: int, status: str = None) -> dict:
    """Lógica para listar e contar quartos e seus status atuais."""
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        query = db.query(models.Room)
        if status:
            query = query.filter(models.Room.status == status.lower())
        
        rooms = query.all()
        return {
            "total_count": len(rooms),
            "rooms": [{"id": r.id, "status": r.status, "price": r.price_per_night, "cap": r.max_capacity} for r in rooms]
        }

def checkout_logic(tenant_id: int, room_id: str, action: str = "preview", payment_method: str = "pix") -> dict:
    """Lógica atômica para prévia e confirmação de encerramento de estadias."""
    from utils.pricing import calculate_daily_rates_count, calculate_reservation_total
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        booking = db.query(models.Booking).filter(models.Booking.room_id == room_id, models.Booking.status == models.BookingStatus.ATIVO).first()
        if not booking: return {"error": f"Nenhum checkout pendente no quarto {room_id}."}

        now = datetime.now()
        days = calculate_daily_rates_count(booking.real_check_in or booking.check_in_date, now, booking.check_in_time, now.strftime("%H:%M"))
        guest_age = 18
        if booking.guest and booking.guest.birth_date:
            bday = booking.guest.birth_date
            guest_age = now.year - bday.year - ((now.month, now.day) < (bday.month, bday.day))
        ages = [guest_age] + [c.age for c in booking.companions]
        settings_dict = {s.key: s.value for s in db.query(models.SystemSetting).all()}
        pricing = calculate_reservation_total(booking.daily_rate, days, ages, settings=settings_dict)
        c_total = sum([c.quantity * c.unit_price for c in booking.consumptions])
        grand_total = pricing["total"] + c_total

        if action == "preview":
            return {"hospede": booking.guest.name, "diarias": days, "total": grand_total}

        if action == "confirm":
            booking.status = models.BookingStatus.CONCLUIDO
            booking.real_check_out = now
            booking.total_amount = grand_total
            room = db.query(models.Room).get(room_id)
            room.status = models.RoomStatus.LIMPEZA
            rev = models.Revenue(
                description=f"Check-out {room_id}", amount=grand_total, category=models.RevenueCategory.HOSPEDAGEM,
                payment_method=payment_method.lower(), booking_id=booking.id, created_at=now
            )
            db.add(rev)
            db.commit()
            return {"success": True, "total": grand_total}

# --- GRUPO FINANCEIRO E RELATÓRIOS ---

def finance_summary_logic(tenant_id: int) -> dict:
    """Lógica atômica para resumo rápido de saúde financeira."""
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        revenues = db.query(models.Revenue).all()
        total = sum(r.amount for r in revenues)
        return {"receita_total": total, "total_transacoes": len(revenues)}

def pdf_generator_logic(tenant_id: int, report_type: str, mode: str = "full", start_date: str = None, end_date: str = None) -> dict:
    """Lógica atômica e motor de geração de arquivos PDF analíticos."""
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        base_url = os.getenv("BASE_URL", "/api")
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Filtros de Data
        end_d = date.today()
        if end_date:
            try: end_d = datetime.strptime(end_date, "%Y-%m-%d").date()
            except: pass
            
        start_d = end_d - timedelta(days=29)
        if start_date:
            try: start_d = datetime.strptime(start_date, "%Y-%m-%d").date()
            except: pass

        start_dt = datetime.combine(start_d, datetime.min.time())
        end_dt   = datetime.combine(end_d,   datetime.max.time())
        
        if report_type == "finance":
            revs = db.query(models.Revenue).filter(
                models.Revenue.created_at >= start_dt,
                models.Revenue.created_at <= end_dt
            ).order_by(models.Revenue.created_at.desc()).all()
            
            exps = db.query(models.Expense).filter(
                models.Expense.is_paid == True,
                models.Expense.paid_date >= start_d,
                models.Expense.paid_date <= end_d
            ).order_by(models.Expense.paid_date.desc()).all()

            total_revenue = sum(r.amount for r in revs)
            total_expense = sum(e.amount for e in exps)
            total_discounts = sum(r.discount or 0.0 for r in revs)
            
            incomes_list = [{"data": r.created_at.strftime("%d/%m/%Y"), "desc": r.description, "cat": r.category.value if r.category else "Geral", "valor": r.amount, "desconto": r.discount or 0.0} for r in revs]
            outcomes_list = [{"data": e.paid_date.strftime("%d/%m/%Y"), "desc": e.description, "cat": e.category.value if e.category else "Geral", "metodo": "Transferência", "valor": e.amount} for e in exps]
            
            # Agrupamentos
            by_category = {}
            for r in revs:
                cat = r.category.value if r.category else "Geral"
                by_category[cat] = by_category.get(cat, 0) + r.amount
            
            expense_by_category = {}
            for e in exps:
                cat = e.category.value if e.category else "Geral"
                expense_by_category[cat] = expense_by_category.get(cat, 0) + e.amount

            # Timeline
            timeline = []
            cursor = start_d
            while cursor <= end_d:
                d_start = datetime.combine(cursor, datetime.min.time())
                d_end = datetime.combine(cursor, datetime.max.time())
                d_rev = sum(r.amount for r in revs if d_start <= r.created_at <= d_end)
                d_exp = sum(e.amount for e in exps if e.paid_date == cursor)
                timeline.append({"date": cursor.strftime("%d/%m/%Y"), "revenue": d_rev, "expense": d_exp, "net": d_rev - d_exp})
                cursor += timedelta(days=1)

            data = {
                "start": start_d.strftime("%d/%m/%Y"), "end": end_d.strftime("%d/%m/%Y"),
                "total_revenue": total_revenue, "total_expense": total_expense, "total_discounts": total_discounts,
                "incomes_list": incomes_list, "outcomes_list": outcomes_list,
                "by_category": by_category, "expense_by_category": expense_by_category,
                "timeline": timeline
            }
            
            filename = f"finance_{ts}.pdf"
            generate_financial_report(data, filename, tenant_id=tenant_id, mode=mode)
            return {
                "url": f"{base_url}/reports/{filename}", 
                "message": f"Relatório financeiro ({mode}) gerado com sucesso.",
                "title": "Relatório Financeiro"
            }
            
        elif report_type == "inventory":
            prods = db.query(models.Product).filter(models.Product.is_active == True).all()
            data = {"total_inventory_value": sum(p.price*p.stock_quantity for p in prods), "products": [{"name": p.name, "stock": p.stock_quantity, "min_stock": p.min_stock, "price": p.price, "category": p.category} for p in prods]}
            filename = f"stock_{ts}.pdf"
            generate_inventory_report(data, filename, tenant_id=tenant_id)
            return {
                "url": f"{base_url}/reports/{filename}",
                "message": "Relatório de estoque gerado.",
                "title": "Relatório de Estoque"
            }
            
        elif report_type == "shopping":
            prods = db.query(models.Product).filter(models.Product.is_active == True).all()
            alert_items = [p for p in prods if p.stock_quantity <= (p.min_stock * 1.5)]
            data = {"items": [{"name": p.name, "category": p.category, "stock": p.stock_quantity, "min_stock": p.min_stock, "is_critical": p.stock_quantity <= p.min_stock, "suggested_buy": max(0, (p.min_stock * 2) - p.stock_quantity), "unit": p.unit_measure or "un", "cost_price": p.cost_price or 0} for p in alert_items]}
            filename = f"shopping_{ts}.pdf"
            generate_shopping_list_report(data, filename, tenant_id=tenant_id)
            return {
                "url": f"{base_url}/reports/{filename}",
                "message": "Lista de compras gerada com base no estoque crítico.",
                "title": "Lista de Compras"
            }
        
        return {"error": "Tipo de relatório inválido."}

def event_manager_logic(tenant_id: int, action: str = "query") -> dict:
    """Lógica atômica para consulta de inteligência de mercado/eventos."""
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        if action == "query":
            q = db.query(models.Event).limit(10)
            events = q.all()
            return {"events": [{"nome": e.name, "data": str(e.start_date)} for e in events]}
        return {"error": "Ação inválida."}


# =============================================================================
# ORQUESTRADOR CENTRAL (AGENTE ADMIN)
# =============================================================================

async def handle_admin_query(message: str, history: list, db: Session, tenant_id: int):
    # --- SELEÇÃO DE MOTOR (GEMINI PREVIEW) ---
    google_key = os.getenv("GOOGLE_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
    
    if google_key:
        llm = ChatGoogleGenerativeAI(model=gemini_model, google_api_key=google_key, temperature=0.1)
        print(f"[AI_ADMIN_LOG] Ativando Motor Supremo: {gemini_model}")
    else:
        llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"), temperature=0.1)
        print(f"[AI_ADMIN_LOG] Usando OpenAI: gpt-4o-mini")

    if not llm: return {"response": "API Key não configurada."}

    # -------------------------------------------------------------------------
    # DEFINIÇÃO DOS MICRO-ROBÔS (Sessões Isoladas)
    # -------------------------------------------------------------------------
    
    @tool
    def robot_inventory_sync(name: str, quantity_change: int = 0, price: float = None, cost_price: float = None, markup_percent: float = None) -> dict:
        """Micro-robô para ENTRADA/SAÍDA de estoque ou CADASTRO de produtos."""
        return inventory_sync_logic(tenant_id, name, quantity_change, price, cost_price=cost_price, markup_percent=markup_percent)

    @tool
    def robot_inventory_viewer(name: str = "", only_alerts: bool = False) -> dict:
        """Micro-robô para CONSULTAR estoque atual ou ver ALERTAS críticos."""
        return inventory_viewer_logic(tenant_id, name, only_alerts)

    @tool
    def robot_room_status_manager(room_id: str, new_status: str, note: str = "") -> dict:
        """Micro-robô especializado em mudar o STATUS (limpeza/manutenção) de quartos."""
        return room_status_logic(tenant_id, room_id, new_status, note)

    @tool
    def robot_room_setup_manager(room_id: str, max_capacity: int = 2, price: float = 150.0, description: str = "", floor: int = 1, room_type: str = "Standard") -> dict:
        """Micro-robô para CADASTRAR novo quarto ou EDITAR preço/capacidade/tipo de um quarto existente."""
        return room_setup_logic(tenant_id, room_id, max_capacity, price, description, floor, room_type)

    @tool
    def robot_consumption_launcher(room_id: str, product_name: str, quantity: int = 1) -> dict:
        """Micro-robô para LANÇAR CONSUMO na conta de um quarto."""
        return consumption_logic(tenant_id, room_id, product_name, quantity)

    @tool
    def robot_checkout_manager(room_id: str, confirm: bool = False, payment_method: str = "pix") -> dict:
        """Micro-robô para CHECKOUT. Use confirm=False para extrato e confirm=True para fechar."""
        action = "confirm" if confirm else "preview"
        return checkout_logic(tenant_id, room_id, action, payment_method)

    @tool
    def robot_finance_summary() -> dict:
        """Micro-robô para RESUMO financeiro rápido."""
        return finance_summary_logic(tenant_id)

    @tool
    def robot_pdf_reporter(report_type: str, mode: str = "full", start_date: str = None, end_date: str = None) -> dict:
        """Micro-robô para GERAR RELATÓRIOS PDF PROFISSIONAIS. 
        Tipos: 'finance' (financeiro), 'inventory' (estoque), 'shopping' (compras).
        Para financeiro, 'mode' pode ser 'full' (completo com extrato e fluxo de caixa) ou 'summary' (apenas KPIs principais).
        Datas no formato YYYY-MM-DD."""
        return pdf_generator_logic(tenant_id, report_type, mode, start_date, end_date)

    @tool
    def robot_event_intelligence(action: str = "query") -> dict:
        """Micro-robô para consultar EVENTOS regionais."""
        return event_manager_logic(tenant_id, action)

    @tool
    def robot_room_viewer(status: str = None) -> dict:
        """Micro-robô para LISTAR QUARTOS e ver seus estados (disponivel, limpeza, ocupado, etc)."""
        return room_viewer_logic(tenant_id, status)

    @tool
    def robot_mark_room_as_ready(room_id: str) -> dict:
        """Micro-robô de EXECUÇÃO IMEDIATA: Use para liberar um quarto, marcar como limpo, pronto ou disponível. 
        Use sempre que o usuário disser algo como 'quarto X pronto', 'quarto X limpo' ou 'liberar quarto X'."""
        return room_status_logic(tenant_id, room_id, "disponivel")

    # --- NOVAS FERRAMENTAS (HABILIDADES DO CUSTOMER AGENT) ---
    @tool
    def robot_check_availability(check_in: str, check_out: str, group_size: int = 1, ages: List[int] = []) -> dict:
        """Micro-robô para consultar vagas e preços. Use sempre que o administrador perguntar sobre disponibilidade ou orçamentos."""
        return shared_tools.availability_check_logic(tenant_id, check_in, check_out, group_size, ages)

    @tool
    def robot_find_guest(cpf: str = "", name: str = "") -> dict:
        """Micro-robô para identificar hóspedes no banco de dados. Use para verificar cadastros existentes."""
        return shared_tools.find_guest_logic(tenant_id, cpf, name)

    @tool
    def robot_book_with_payment(guest_id: int, room_id: str, check_in: str, check_out: str, group_size: int, companions: List[dict] = []) -> dict:
        """Micro-robô FINALIZADOR: Realiza a reserva e gera a cobrança PIX. Use para efetivar a venda para o cliente."""
        return shared_tools.unified_booking_flow(tenant_id, guest_id, room_id, check_in, check_out, group_size, companions)

    @tool
    def robot_find_booking(cpf: str = "", name: str = "", room_id: str = "") -> dict:
        """Micro-robô de INVESTIGAÇÃO: Localiza IDs de reserva e detalhes por CPF, Nome do hóspede ou número do quarto. 
        Use sempre que não souber o ID da reserva ou precisar descobrir quem está em qual quarto."""
        return shared_tools.find_booking_logic(tenant_id, cpf, name, room_id)

    @tool
    def robot_get_payment_info(booking_id: int) -> dict:
        """Micro-robô de COBRANÇA: Gera ou recupera o QR Code PIX e dados de pagamento para uma reserva existente."""
        return shared_tools.payment_info_logic(tenant_id, booking_id)

    @tool
    def robot_confirm_payment(booking_id: int, method: str = "pix") -> dict:
        """Micro-robô financeiro: Confirma pagamentos manualmente e libera a reserva. Use para dar baixa em depósitos."""
        return shared_tools.confirm_payment_logic(tenant_id, booking_id, method)

    @tool
    def robot_record_knowledge(content: str, category: str = "geral", importance: int = 1, guest_id: int = None) -> dict:
        """Micro-robô de Memória: Salva fatos, preferências ou regras aprendidas na memória de longo prazo."""
        return shared_tools.store_operational_memory_logic(tenant_id, content, category, guest_id, importance)

    # --- MEMÓRIA E DIAGNÓSTICO ---
    current_guest_id = None
    for h in reversed(history):
        if h.get("guest_id"): 
            current_guest_id = h["guest_id"]
            break
            
    op_memory = shared_tools.get_operational_memory_logic(tenant_id, current_guest_id)
    if op_memory: print(f"[AI_ADMIN_LOG] Carregados fatos da memória operacional.")

    # -------------------------------------------------------------------------
    # ORQUESTRAÇÃO
    # -------------------------------------------------------------------------

    tools = [
        robot_inventory_sync, robot_inventory_viewer, robot_room_status_manager,
        robot_room_setup_manager, robot_consumption_launcher, robot_checkout_manager, 
        robot_finance_summary, robot_pdf_reporter, robot_event_intelligence,
        robot_room_viewer, robot_mark_room_as_ready,
        robot_check_availability, robot_find_guest, robot_book_with_payment,
        robot_find_booking, robot_get_payment_info, robot_confirm_payment, robot_record_knowledge
    ]
    llm_with_tools = llm.bind_tools(tools)
    
    sys_msg = SystemMessage(content=f"""Você é o ORQUESTRADOR MESTRE e GERENTE GERAL do estabelecimento.
DIRETRIZES DE COMUNICAÇÃO:
1. **NARRATIVA DE PROGRESSO**: Seja transparente. Se for acionar um motor de relatórios ou estoque, avise brevemente: "Entendido, estou acessando os dados financeiros agora..." ou "Vou verificar a disponibilidade nos quartos para você...".
2. **FEEDBACK OBRIGATÓRIO**: Após o retorno de qualquer ferramenta, você DEVE confirmar o resultado ao usuário. NUNCA envie respostas vazias.
3. **DIFICULDADES E PERMISSÕES**: Caso não tenha permissão para algo ou encontre um erro técnico no robô, explique: "Infelizmente meu acesso ao histórico de faturamento está restrito no momento" ou "Encontrei uma dificuldade para gerar seu arquivo agora, pode tentar novamente?".
4. **MEMÓRIA OPERACIONAL**:
{op_memory}

Sua postura é de um gerente sênior: resolutivo, preciso e pragmático.""")

    def call_model(state: MessagesState):
        messages = [sys_msg] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", lambda s: "tools" if s["messages"][-1].tool_calls else END)
    workflow.add_edge("tools", "agent")
    app = workflow.compile()

    # Conversão de histórico para LangChain de forma robusta
    lc_messages = convert_history_to_langchain(history)
    lc_messages.append(HumanMessage(content=message))

    try:
        final_state = await app.ainvoke({"messages": lc_messages})
        response_msg = final_state["messages"][-1]
        response_content = response_msg.content
        
        # --- NORMALIZAÇÃO NATIVA (THE GEMINI WAY) ---
        # Extrai o texto se vier em formato de lista (Multimodal)
        if isinstance(response_content, list):
            full_text = ""
            for part in response_content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        full_text += part.get("text", "")
                elif isinstance(part, str):
                    full_text += part
            response_content = full_text.strip()
        
        # Fallback para mensagens sem texto mas com chamadas de ferramenta pendentes
        if not response_content and hasattr(response_msg, 'tool_calls') and response_msg.tool_calls:
            response_content = "Processando sua solicitação... 🤖"

        # VÁLVULA DE ESCAPE: Se a IA ficou muda APÓS a execução das ferramentas
        if not response_content or response_content.strip() == "":
            last_tool_msg = next((m for m in reversed(final_state["messages"]) if isinstance(m, ToolMessage)), None)
            if last_tool_msg:
                try:
                    import json
                    res_j = json.loads(last_tool_msg.content)
                    msg_info = res_j.get("message") or res_j.get("error") or "Solicitação processada com sucesso."
                    url_pdf = res_j.get("url")
                    title_pdf = res_j.get("title") or "Baixar Arquivo"
                    response_content = f"{msg_info}"
                    if url_pdf: response_content += f"\n\n[{title_pdf}]({url_pdf})"
                except:
                    response_content = "Seu robô completou a tarefa com sucesso. Algo mais em que posso ajudar?"
            else:
                response_content = "Entendido. No que posso te ajudar agora?"

        return {"response": response_content}
    except Exception as e:
        print(f"[ADMIN_ERROR]: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"response": f"Erro na orquestração suprema: {str(e)}"}
