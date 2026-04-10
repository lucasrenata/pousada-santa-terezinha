import json
import os
from sqlalchemy.orm import Session
import models
from utils.pdf_reports import generate_financial_report, generate_inventory_report
from datetime import datetime, date, timedelta
from typing import Optional, List

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode

def get_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "sua_chave_aqui":
        return None
    return ChatOpenAI(model="gpt-4o-mini", api_key=api_key, temperature=0.1)

async def handle_admin_query(message: str, history: list, db: Session):
    llm = get_llm()
    if not llm:
        return {"response": "A chave da OpenAI não foi configurada. Por favor, adicione sua API Key no arquivo .env."}

    # =========================================================================
    # ROBÔ 1: ESTOQUE (Smart Inventory Robot)
    # =========================================================================
    @tool
    def smart_inventory_manager(action: str, name: str = "", quantity_change: int = 0, price: float = None, category: str = None, barcode: str = "") -> dict:
        """
        Robô completo para gestão de estoque.
        Ações: 'sync' (lançar/atualizar/cadastrar), 'list' (ver estoque), 'alerts' (nível crítico).
        """
        if action == "alerts":
            low = db.query(models.Product).filter(models.Product.stock_quantity <= models.Product.min_stock, models.Product.is_active == True).all()
            return {"alerts": [{"name": p.name, "stock": p.stock_quantity, "min": p.min_stock} for p in low]}

        if action == "list":
            query = db.query(models.Product).filter(models.Product.is_active == True)
            if name: query = query.filter(models.Product.name.ilike(f"%{name}%"))
            prods = query.all()
            return {"products": [{"id": p.id, "name": p.name, "stock": p.stock_quantity, "price": p.price, "cat": p.category} for p in prods]}

        if action == "sync":
            if not name: return {"error": "Nome do produto é obrigatório para sincronização."}
            
            # Tenta busca exata ou similar
            existing = db.query(models.Product).filter(models.Product.name.ilike(f"{name}")).first()
            if not existing:
                existing = db.query(models.Product).filter(models.Product.name.ilike(f"%{name}%")).first()

            if existing:
                # ATUALIZAÇÃO
                old_stock = existing.stock_quantity
                existing.stock_quantity += quantity_change
                if price is not None: existing.price = price
                if category: existing.category = category
                if barcode: existing.barcode = barcode
                db.commit()
                return {
                    "status": "updated",
                    "product": existing.name,
                    "old_stock": old_stock,
                    "new_stock": existing.stock_quantity,
                    "message": f"Produto '{existing.name}' atualizado com sucesso."
                }
            else:
                # CRIAÇÃO
                if price is None: price = 0.0
                if not category: category = "Diversos"
                try:
                    new_p = models.Product(
                        name=name, price=price, category=category, 
                        stock_quantity=quantity_change, barcode=barcode or None
                    )
                    db.add(new_p)
                    db.commit()
                    db.refresh(new_p)
                    return {
                        "status": "created",
                        "product": new_p.name,
                        "stock": new_p.stock_quantity,
                        "message": f"Novo produto '{new_p.name}' cadastrado e estoque inicial lançado."
                    }
                except Exception as e:
                    db.rollback()
                    return {"error": f"Falha ao criar produto: {str(e)}"}

        return {"error": "Ação inválida para o robô de estoque."}

    # =========================================================================
    # ROBÔ 2: OPERAÇÕES (Smart Operations Robot)
    # =========================================================================
    @tool
    def smart_operation_manager(room_id: str, action: str, product_name: str = "", quantity: int = 1, payment_method: str = "pix", new_status: str = "", note: str = "") -> dict:
        """
        Robô para gestão de quartos, consumos e checkouts.
        Ações: 
        - 'status': Muda o status do quarto. Requer 'new_status' (disponivel, limpeza, manutencao).
        - 'consumption': Lança item no quarto. Requer 'product_name' e 'quantity'.
        - 'checkout_preview': Gera extrato da conta.
        - 'checkout_confirm': Finaliza check-out. Requer 'payment_method'.
        """
        from utils.pricing import calculate_daily_rates_count, calculate_reservation_total
        
        room = db.query(models.Room).filter(models.Room.id == room_id).first()
        if not room: return {"error": f"Quarto {room_id} não existe."}

        # --- AÇÃO: STATUS ---
        if action == "status":
            valid = ["disponivel", "limpeza", "manutencao"]
            # Fallback caso o LLM mande o status no campo 'note'
            target_status = (new_status or note or "").lower()
            
            # Normalização de termos comuns
            if "liber" in target_status or "dispon" in target_status: target_status = "disponivel"
            if "limp" in target_status: target_status = "limpeza"
            if "manut" in target_status: target_status = "manutencao"

            if target_status not in valid:
                return {"error": f"Status '{target_status}' inválido. Use: {', '.join(valid)}"}
            
            old_status = room.status
            room.status = target_status
            if target_status == "manutencao": 
                room.maintenance_note = note if note else "Manutenção solicitada via Agente"
            elif target_status == "disponivel":
                room.maintenance_note = None
            
            db.commit()
            return {"success": True, "message": f"Quarto {room_id} alterado de '{old_status}' para '{target_status}'."}

        # --- AÇÃO: CONSUMO ---
        if action == "consumption":
            booking = db.query(models.Booking).filter(models.Booking.room_id == room_id, models.Booking.status == models.BookingStatus.ATIVO).first()
            if not booking: return {"error": "Sem check-in ativo para lançar consumo."}
            
            # Usa o robô de estoque para validar o produto
            p_res = smart_inventory_manager.invoke({"action": "list", "name": product_name})
            if not p_res.get("products"): return {"error": f"Produto '{product_name}' não encontrado no estoque."}
            
            p_data = p_res["products"][0]
            prod = db.query(models.Product).get(p_data["id"])
            
            if prod.stock_quantity < quantity: return {"error": f"Estoque insuficiente ({prod.stock_quantity})."}
            
            cons = models.Consumption(booking_id=booking.id, product_id=prod.id, quantity=quantity, unit_price=prod.price)
            prod.stock_quantity -= quantity
            db.add(cons)
            db.commit()
            return {"success": True, "message": f"Lançado {quantity}x {prod.name} no quarto {room_id}."}

        # --- AÇÃO: CHECKOUT (Preview ou Confirm) ---
        if action in ["checkout_preview", "checkout_confirm"]:
            booking = db.query(models.Booking).filter(models.Booking.room_id == room_id, models.Booking.status == models.BookingStatus.ATIVO).first()
            if not booking: return {"error": "Nenhum check-in ativo para checkout."}

            # Cálculos
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

            if action == "checkout_preview":
                return {
                    "hospede": booking.guest.name if booking.guest else "N/A",
                    "diarias": days,
                    "valor_hospedagem": pricing["total"],
                    "valor_consumo": c_total,
                    "total_geral": grand_total,
                    "consumos": [{"item": c.product.name, "qtd": c.quantity} for c in booking.consumptions]
                }

            if action == "checkout_confirm":
                booking.status = models.BookingStatus.CONCLUIDO
                booking.real_check_out = now
                booking.total_amount = grand_total
                room.status = models.RoomStatus.LIMPEZA
                
                rev = models.Revenue(
                    description=f"Check-out {room_id} - {booking.guest.name if booking.guest else ''}",
                    amount=grand_total, category=models.RevenueCategory.HOSPEDAGEM,
                    payment_method=payment_method.lower(), booking_id=booking.id, created_at=now
                )
                db.add(rev)
                db.commit()
                return {"success": True, "total": grand_total, "metodo": payment_method.upper(), "message": "Check-out finalizado com sucesso."}

        return {"error": "Ação operacional inválida."}

    # =========================================================================
    # ROBÔ 3: EVENTOS (Smart Event Robot)
    # =========================================================================
    @tool
    def smart_event_manager(action: str, name: str = "", month: int = None, start_date: str = "", end_date: str = "") -> dict:
        """Robô para consultar e gerenciar o calendário de eventos regionais."""
        if action == "query":
            import calendar
            q = db.query(models.Event)
            if name: q = q.filter(models.Event.name.ilike(f"%{name}%"))
            elif month:
                y = datetime.now().year
                _, last = calendar.monthrange(y, month)
                q = q.filter(models.Event.end_date >= date(y, month, 1), models.Event.start_date <= date(y, month, last))
            else:
                q = q.filter(models.Event.start_date >= datetime.now().date()).limit(10)
            
            events = q.all()
            total_rooms = db.query(models.Room).count()
            res = []
            for e in events:
                occ = db.query(models.Booking.room_id).filter(
                    models.Booking.status.in_([models.BookingStatus.CONFIRMADO, models.BookingStatus.ATIVO]),
                    models.Booking.check_out_date >= e.start_date, models.Booking.check_in_date <= e.end_date
                ).distinct().count()
                res.append({
                    "id": e.id, "nome": e.name, "data": f"{e.start_date} a {e.end_date}",
                    "vagas": f"{total_rooms - occ} de {total_rooms}", "loc": e.location
                })
            return {"events": res}

        if action == "add":
            try:
                sd = datetime.strptime(start_date, "%Y-%m-%d").date()
                ed = datetime.strptime(end_date, "%Y-%m-%d").date()
                ev = models.Event(name=name, start_date=sd, end_date=ed, location="Região")
                db.add(ev)
                db.commit()
                return {"success": True, "message": f"Evento '{name}' adicionado."}
            except: return {"error": "Formato de data inválido (use YYYY-MM-DD)."}

        return {"error": "Ação de eventos inválida."}

    # =========================================================================
    # ROBÔ 4: FINANCEIRO E RELATÓRIOS (Smart Finance Robot)
    # =========================================================================
    @tool
    def smart_finance_robot(action: str, type: str = "summary") -> dict:
        """Robô para relatórios financeiros e de estoque. Ações: 'view', 'pdf'."""
        if action == "view":
            revenues = db.query(models.Revenue).all()
            total = sum(r.amount for r in revenues)
            return {"total_revenue": total, "entries": len(revenues), "period": "Geral"}
        
        if action == "pdf":
            base_url = os.getenv("BASE_URL", "http://localhost:8000")
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            if type == "finance":
                data = {"total_revenue": sum(r.amount for r in db.query(models.Revenue).all())}
                path = generate_financial_report(data, f"finance_{ts}.pdf")
                return {"url": f"{base_url}/reports/finance_{ts}.pdf"}
            else:
                prods = db.query(models.Product).all()
                data = {"products": [{"name": p.name, "stock": p.stock_quantity} for p in prods]}
                path = generate_inventory_report(data, f"stock_{ts}.pdf")
                return {"url": f"{base_url}/reports/stock_{ts}.pdf"}
                
        return {"error": "Ação financeira inválida."}

    # =========================================================================
    # CONFIGURAÇÃO DO AGENTE
    # =========================================================================
    tools = [smart_inventory_manager, smart_operation_manager, smart_event_manager, smart_finance_robot]
    llm_with_tools = llm.bind_tools(tools)

    sys_msg = SystemMessage(content="""Você é o Cérebro Operacional da Pousada.
Sua missão é extrair a intenção do usuário e enviar para os Robôs Python especializados.

DIRETRIZES:
1. **ESTOQUE**: 'smart_inventory_manager' (action='sync'). Se o usuário disser "Lança X", não pergunte nada, apenas chame o robô com a quantidade. Se ele não informar preço/categoria, o robô usará padrões.
2. **QUARTOS/CONTAS**: 'smart_operation_manager'. Lida com consumo, status (limpeza/manutenção) e checkout.
3. **EVENTOS**: 'smart_event_manager' (action='query'). 
4. **FINANCEIRO**: 'smart_finance_robot'.
5. **DÊ ORDENS DIRETAS**: Não hesite. Se o comando for claro, execute. Só peça confirmação para EXCLUIR algo permanentemente.
6. **RESPOSTAS**: Seja curto, grosso e eficiente. Reporte o sucesso e os novos dados (ex: 'Arroz lançado. Novo estoque: 15').""")

    def call_model(state: MessagesState):
        messages = [sys_msg] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    # Graph
    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", lambda s: "tools" if s["messages"][-1].tool_calls else END)
    workflow.add_edge("tools", "agent")
    app = workflow.compile()

    # History Execution
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
        import traceback
        traceback.print_exc()
        return {"response": "Erro na execução dos robôs operacionais."}
