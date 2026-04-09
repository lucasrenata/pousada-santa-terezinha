import json
import os
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
import models
from utils.pdf_reports import generate_financial_report, generate_inventory_report
from datetime import datetime

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode

def get_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "sua_chave_aqui":
        return None
    return ChatOpenAI(model="gpt-4o-mini", api_key=api_key, temperature=0.3)

async def handle_admin_query(message: str, history: list, db: Session):
    llm = get_llm()
    if not llm:
        return {"response": "A chave da OpenAI não foi configurada. Por favor, adicione sua API Key no arquivo .env para ativar o chat admin."}

    # --- TOOLS DYNAMICS ---

    @tool
    def get_finance_summary() -> dict:
        """Obtém um resumo financeiro das receitas da pousada."""
        revenues = db.query(models.Revenue).all()
        total = sum(r.amount for r in revenues)
        
        by_category = {}
        for r in revenues:
            cat = r.category.value if hasattr(r.category, 'value') else str(r.category)
            by_category[cat] = by_category.get(cat, 0) + r.amount
            
        return {
            "period": "Geral (Até o momento)",
            "total_revenue": total,
            "transactions": len(revenues),
            "by_category": by_category
        }

    @tool
    def generate_pdf_finance_report() -> dict:
        """Gera um arquivo PDF com o relatório financeiro atual."""
        data = get_finance_summary.invoke({})
        filename = f"relatorio_financeiro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        path = generate_financial_report(data, filename)
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        return {
            "message": "Relatório Financeiro PDF gerado com sucesso", 
            "download_url": f"{base_url}/reports/{filename}", 
            "path": path
        }

    @tool
    def generate_pdf_inventory_report() -> dict:
        """Gera um arquivo PDF com o relatório de estoque completo e lista de compras."""
        products = db.query(models.Product).all()
        data = {
            "products": [{"name": p.name, "stock": p.stock_quantity, "min_stock": p.min_stock} for p in products]
        }
        filename = f"relatorio_estoque_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        path = generate_inventory_report(data, filename)
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        return {
            "message": "Relatório de Estoque e Compras PDF gerado com sucesso", 
            "download_url": f"{base_url}/reports/{filename}", 
            "path": path
        }

    @tool
    def get_stock_alerts() -> list:
        """Lista apenas produtos com estoque crítico (abaixo de 5 unidades)."""
        products = db.query(models.Product).filter(models.Product.stock_quantity < 5).all()
        return [{"name": p.name, "stock": p.stock_quantity, "price": p.price, "min_stock": p.min_stock} for p in products]

    @tool
    def get_full_inventory() -> list:
        """Lista todos os produtos cadastrados no sistema e suas quantidades totais."""
        products = db.query(models.Product).all()
        return [{"name": p.name, "stock": p.stock_quantity, "category": p.category} for p in products]

    @tool
    def search_product_by_name(name: str) -> list:
        """Busca um produto específico pelo nome para saber preço ou quantidade exata."""
        products = db.query(models.Product).filter(models.Product.name.ilike(f"%{name}%")).all()
        return [{"name": p.name, "stock": p.stock_quantity, "price": p.price, "category": p.category} for p in products]

    @tool
    def get_rooms_overview() -> dict:
        """Obtém um panorama completo dos quartos: quantos estão disponíveis, ocupados, em limpeza e em manutenção."""
        rooms = db.query(models.Room).all()
        status_count = {"disponivel": 0, "ocupado": 0, "limpeza": 0, "manutencao": 0}
        details = {"disponivel": [], "ocupado": [], "limpeza": [], "manutencao": []}
        for r in rooms:
            s = r.status.value if hasattr(r.status, 'value') else str(r.status)
            status_count[s] = status_count.get(s, 0) + 1
            details[s].append({"quarto": r.id, "tipo": r.type, "capacidade": r.max_capacity})
        return {
            "total_quartos": len(rooms),
            "resumo": status_count,
            "detalhes": details
        }

    @tool
    def get_bookings_overview(start_date: str = "", end_date: str = "") -> dict:
        """Obtém um panorama das reservas. Se datas forem informadas (YYYY-MM-DD), filtra pelo período. Caso contrário, mostra todas as reservas ativas/pendentes/confirmadas."""
        from datetime import datetime as dt
        query = db.query(models.Booking)
        
        if start_date and end_date:
            try:
                sd = dt.strptime(start_date, "%Y-%m-%d")
                ed = dt.strptime(end_date, "%Y-%m-%d")
                query = query.filter(
                    models.Booking.check_out_date >= sd,
                    models.Booking.check_in_date <= ed
                )
            except:
                pass
        else:
            query = query.filter(models.Booking.status.in_([
                models.BookingStatus.PENDENTE, 
                models.BookingStatus.CONFIRMADO, 
                models.BookingStatus.ATIVO
            ]))
        
        bookings = query.all()
        status_count = {}
        booking_list = []
        for b in bookings:
            s = b.status.value if hasattr(b.status, 'value') else str(b.status)
            status_count[s] = status_count.get(s, 0) + 1
            guest = db.query(models.Guest).filter(models.Guest.id == b.guest_id).first()
            booking_list.append({
                "id": b.id,
                "hospede": guest.name if guest else "N/A",
                "quarto": b.room_id,
                "check_in": str(b.check_in_date),
                "check_out": str(b.check_out_date),
                "status": s,
                "total": b.total_amount,
                "pagamento": b.payment_status.value if hasattr(b.payment_status, 'value') else str(b.payment_status)
            })
        return {
            "total_reservas": len(bookings),
            "por_status": status_count,
            "reservas": booking_list
        }

    @tool
    def get_daily_dashboard() -> dict:
        """Retorna um painel geral do dia: quartos, reservas ativas, estoque crítico e faturamento. Use quando o admin pedir um 'resumo geral' ou 'status do sistema'."""
        from datetime import datetime as dt, date
        
        # Quartos
        rooms = db.query(models.Room).all()
        room_status = {}
        for r in rooms:
            s = r.status.value if hasattr(r.status, 'value') else str(r.status)
            room_status[s] = room_status.get(s, 0) + 1
        
        # Reservas ativas hoje
        today = date.today()
        active_bookings = db.query(models.Booking).filter(
            models.Booking.status.in_([models.BookingStatus.ATIVO, models.BookingStatus.CONFIRMADO]),
            models.Booking.check_in_date <= dt.combine(today, dt.max.time()),
            models.Booking.check_out_date >= dt.combine(today, dt.min.time())
        ).count()
        
        # Check-ins previstos hoje
        checkins_today = db.query(models.Booking).filter(
            models.Booking.status.in_([models.BookingStatus.PENDENTE, models.BookingStatus.CONFIRMADO]),
            models.Booking.check_in_date >= dt.combine(today, dt.min.time()),
            models.Booking.check_in_date <= dt.combine(today, dt.max.time())
        ).count()
        
        # Check-outs previstos hoje
        checkouts_today = db.query(models.Booking).filter(
            models.Booking.status.in_([models.BookingStatus.ATIVO, models.BookingStatus.CONFIRMADO]),
            models.Booking.check_out_date >= dt.combine(today, dt.min.time()),
            models.Booking.check_out_date <= dt.combine(today, dt.max.time())
        ).count()
        
        # Estoque crítico
        critical_stock = db.query(models.Product).filter(models.Product.stock_quantity < 5).count()
        
        # Faturamento total
        total_revenue = sum(r.amount for r in db.query(models.Revenue).all())
        
        # Hóspedes cadastrados
        total_guests = db.query(models.Guest).count()
        
        return {
            "data_atual": str(today),
            "quartos": {"total": len(rooms), **room_status},
            "reservas_ativas_hoje": active_bookings,
            "checkins_previstos_hoje": checkins_today,
            "checkouts_previstos_hoje": checkouts_today,
            "produtos_estoque_critico": critical_stock,
            "faturamento_total": total_revenue,
            "hospedes_cadastrados": total_guests
        }

    @tool
    def get_events_availability(event_name: str = "") -> list:
        """Busca eventos regionais e verifica se há quartos disponíveis nessas datas. Use quando perguntarem sobre vagas para um evento específico ou quais os próximos eventos e a situação do hotel."""
        from datetime import datetime as dt
        # 1. Buscar os eventos
        event_query = db.query(models.Event)
        if event_name:
            event_query = event_query.filter(models.Event.name.ilike(f"%{event_name}%"))
        else:
            # Pega os 5 próximos eventos a partir de hoje
            event_query = event_query.filter(models.Event.start_date >= dt.now().date()).order_by(models.Event.start_date.asc()).limit(5)
            
        events = event_query.all()
        if not events:
            return {"message": "Nenhum evento regional encontrado para os critérios informados."}

        # 2. Total de quartos cadastrados
        total_rooms = db.query(models.Room).count()
        
        results = []
        for e in events:
            # 3. Verificar ocupação no período do evento
            # Conta quantos QUARTOS DISTINTOS possuem reservas confirmadas ou ativas no período
            overlapping_rooms = db.query(models.Booking.room_id).filter(
                models.Booking.status.in_([models.BookingStatus.CONFIRMADO, models.BookingStatus.ATIVO]),
                models.Booking.check_out_date >= e.start_date,
                models.Booking.check_in_date <= e.end_date
            ).distinct().all()
            
            occupied_count = len(overlapping_rooms)
            available_count = total_rooms - occupied_count
            
            results.append({
                "evento": e.name,
                "periodo": f"{e.start_date.strftime('%d/%m')} até {e.end_date.strftime('%d/%m')}",
                "local": e.location,
                "vagas": f"{available_count} de {total_rooms} quartos disponíveis",
                "esgotado": available_count <= 0
            })
            
        return results

    tools = [get_finance_summary, generate_pdf_finance_report, generate_pdf_inventory_report, get_stock_alerts, get_full_inventory, search_product_by_name, get_rooms_overview, get_bookings_overview, get_daily_dashboard, get_events_availability]
    llm_with_tools = llm.bind_tools(tools)
 
    # --- LANGGRAPH SETUP ---
    sys_msg = SystemMessage(content="""Você é o Assistente Administrativo da Pousada System.
Seu papel é ajudar o administrador com dados financeiros, estoque, quartos, reservas, eventos e relatórios.

DIRETRIZES:
1. **Visão Geral / Dashboard**: Se pedirem "resumo", "status", "como está a pousada" → use 'get_daily_dashboard'.
2. **Quartos**: Se perguntarem sobre quartos disponíveis, sujos, em manutenção → use 'get_rooms_overview'.
3. **Reservas**: Se perguntarem sobre reservas em um período → use 'get_bookings_overview' com as datas. Se só pedirem reservas ativas → use sem datas.
4. **Eventos e Vagas**: Se perguntarem se "há vagas para o evento X", "quais os eventos do mês" ou "como está a ocupação nos dias de evento" → use 'get_events_availability'.
5. **PDF Financeiro**: Se solicitarem PDF de faturamento → use 'generate_pdf_finance_report'.
6. **PDF Estoque**: Se solicitarem PDF de estoque/inventário → use 'generate_pdf_inventory_report'.
7. **Links**: Retorne links SEMPRE em Markdown clicável: [📄 Baixar Relatório](URL).
8. **Estoque**: Para alertas use 'get_stock_alerts'. Para inventário completo use 'get_full_inventory'. Para buscar item específico use 'search_product_by_name'.
9. **Apresentação**: Formate respostas com negrito, listas e emojis para facilitar a leitura rápida.""")

    def call_model(state: MessagesState):
        messages = [sys_msg] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    
    workflow.add_edge(START, "agent")
    
    def should_continue(state: MessagesState):
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        return END

    workflow.add_conditional_edges("agent", should_continue)
    workflow.add_edge("tools", "agent")
    
    app = workflow.compile()

    # --- EXECUTION ---
    lc_messages = []
    for h in history[-15:]:
        if isinstance(h, dict):
            role = h.get("role", "user")
            content = h.get("content", "")
            if role == "user": lc_messages.append(HumanMessage(content=content))
            elif role == "assistant": lc_messages.append(AIMessage(content=content))
    
    lc_messages.append(HumanMessage(content=message))
    
    try:
        final_state = await app.ainvoke({"messages": lc_messages})
        final_message = final_state["messages"][-1].content
        return {"response": final_message}
    except Exception as e:
        print(f"❌ Erro LangGraph no Agente Admin: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"response": "Desculpe, tive um problema ao acessar os dados administrativos agora (Erro LangGraph)."}
