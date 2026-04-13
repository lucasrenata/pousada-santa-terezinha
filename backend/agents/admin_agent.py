import json
import os
from sqlalchemy.orm import Session
import models
from database import SessionLocal, set_tenant_context
from utils.pdf_reports import generate_financial_report, generate_inventory_report, generate_shopping_list_report
from datetime import datetime, date, timedelta
from typing import Optional, List

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode

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

def pdf_generator_logic(tenant_id: int, report_type: str) -> dict:
    """Lógica atômica e motor de geração de arquivos PDF analíticos."""
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if report_type == "finance":
            revs = db.query(models.Revenue).all()
            total_revenue = sum(r.amount for r in revs)
            data = {"total_revenue": total_revenue, "transactions": len(revs), "avg_ticket": total_revenue/len(revs) if len(revs)>0 else 0, "by_category": {}, "by_method": {}}
            generate_financial_report(data, f"finance_{ts}.pdf")
            return {"url": f"{base_url}/reports/finance_{ts}.pdf"}
            
        elif report_type == "inventory":
            prods = db.query(models.Product).filter(models.Product.is_active == True).all()
            data = {"total_inventory_value": sum(p.price*p.stock_quantity for p in prods), "products": [{"name": p.name, "stock": p.stock_quantity, "min_stock": p.min_stock, "price": p.price, "category": p.category} for p in prods]}
            generate_inventory_report(data, f"stock_{ts}.pdf")
            return {"url": f"{base_url}/reports/stock_{ts}.pdf"}
            
        elif report_type == "shopping":
            prods = db.query(models.Product).filter(models.Product.is_active == True).all()
            alert_items = [p for p in prods if p.stock_quantity <= (p.min_stock * 1.5)]
            data = {"items": [{"name": p.name, "category": p.category, "stock": p.stock_quantity, "min_stock": p.min_stock, "is_critical": p.stock_quantity <= p.min_stock, "suggested_buy": max(0, (p.min_stock * 2) - p.stock_quantity), "unit": p.unit_measure or "un"} for p in alert_items]}
            generate_shopping_list_report(data, f"shopping_{ts}.pdf")
            return {"url": f"{base_url}/reports/shopping_{ts}.pdf"}
        
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

def get_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key: return None
    return ChatOpenAI(model="gpt-4o-mini", api_key=api_key, temperature=0.1)

async def handle_admin_query(message: str, history: list, db: Session, tenant_id: int):
    llm = get_llm()
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
    def robot_pdf_reporter(report_type: str) -> dict:
        """Micro-robô para GERAR PDF. Tipos: 'finance', 'inventory', 'shopping'."""
        return pdf_generator_logic(tenant_id, report_type)

    @tool
    def robot_event_intelligence(action: str = "query") -> dict:
        """Micro-robô para consultar EVENTOS regionais."""
        return event_manager_logic(tenant_id, action)

    @tool
    def robot_room_viewer(status: str = None) -> dict:
        """Micro-robô para LISTAR QUARTOS e ver seus estados (disponivel, limpeza, ocupado, etc)."""
        return room_viewer_logic(tenant_id, status)

    # -------------------------------------------------------------------------
    # ORQUESTRAÇÃO
    # -------------------------------------------------------------------------

    tools = [
        robot_inventory_sync, robot_inventory_viewer, robot_room_status_manager,
        robot_room_setup_manager, robot_consumption_launcher, robot_checkout_manager, 
        robot_finance_summary, robot_pdf_reporter, robot_event_intelligence,
        robot_room_viewer
    ]
    llm_with_tools = llm.bind_tools(tools)
    
    sys_msg = SystemMessage(content="""Você é o ORQUESTRADOR MESTRE da Pousada.
Sua missão é coordenar uma equipe de Micro-Robôs especializados para realizar as tarefas.

DIRETRIZES:
1. **CADASTRO DE QUARTOS**: Se o usuário quiser criar ou configurar quartos, use 'robot_room_setup_manager'.
2. **CONSUMO**: Se pedirem "lança X no quarto Y", ative o 'robot_consumption_launcher'.
3. **CHECKOUT**: Se pedirem extrato ou saída do quarto, use 'robot_checkout_manager'.
4. **RELATÓRIOS ANALÍTICOS**: Use 'robot_pdf_reporter'.
5. **RESPOSTAS**: Execute e reporte o feedback. Forneça links para PDFs.""")

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

    # Conversão de histórico para LangChain
    lc_messages = []
    for h in history[-10:]:
        role = h.get("role", "user")
        if role == "user": lc_messages.append(HumanMessage(content=h.get("content", "")))
        elif role == "assistant": lc_messages.append(AIMessage(content=h.get("content", "")))
    lc_messages.append(HumanMessage(content=message))

    try:
        final_state = await app.ainvoke({"messages": lc_messages})
        return {"response": final_state["messages"][-1].content}
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        return {"response": "Erro na orquestração dos robôs. Certifique-se de que a OpenAI API Key está correta."}
