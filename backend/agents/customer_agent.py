import json
import os
from datetime import datetime, date
from sqlalchemy.orm import Session
import models
from utils.pricing import calculate_daily_rates_count, calculate_reservation_total

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

async def handle_customer_query(message: str, history: list, db: Session):
    llm = get_llm()
    if not llm:
        return {"response": "A chave da OpenAI não foi configurada. Por favor, adicione sua API Key no arquivo .env."}

    # --- TOOLS DYNAMICS ---
    @tool
    def get_current_context() -> dict:
        """Obtém a data e hora atuais da pousada e as configurações de precificação ativas."""
        now = datetime.now()
        days = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
        
        # Busca modelo de precificação
        settings_rows = db.query(models.SystemSetting).all()
        settings_dict = {s.key: s.value for s in settings_rows}
        pricing_model = settings_dict.get("pousada_pricing_model", "per_person") # per_person ou per_room
        
        return {
            "current_date": now.strftime("%Y-%m-%d"),
            "current_time": now.strftime("%H:%M:%S"),
            "day_of_week": days[now.weekday()],
            "check_in_standard": "14:00",
            "check_out_standard": "14:00",
            "pricing_model_active": pricing_model # Importante para explicar o valor ao hóspede
        }

    @tool
    def find_guest_by_cpf(cpf: str) -> dict:
        """Busca um hóspede no banco de dados pelo CPF. Use o CPF com ou sem pontuação."""
        clean_cpf = "".join(filter(str.isdigit, cpf))
        search_pattern = "%" + "%".join(clean_cpf) + "%"
        guest = db.query(models.Guest).filter(models.Guest.document.ilike(search_pattern)).first()
        if guest:
            return {"id": guest.id, "name": guest.name, "email": guest.email, "phone": guest.phone, "document": guest.document}
        return {"error": "Hóspede não encontrado."}

    @tool
    def find_guests_by_name(name: str) -> list:
        """Busca hóspedes pelo nome quando o CPF não é informado ou conhecido."""
        guests = db.query(models.Guest).filter(models.Guest.name.ilike(f"%{name}%")).all()
        return [{"id": g.id, "name": g.name, "document": g.document, "phone": g.phone} for g in guests]

    @tool
    def check_availability(check_in: str, check_out: str, capacity: int = 1) -> dict:
        """Verifica quais quartos estão disponíveis em um período.
        RETORNO: Lista de quartos e a CAPACIDADE TOTAL disponível.
        IMPORTANTE: Se o grupo for grande (ex: 20 pessoas), use a lista de quartos para sugerir uma combinação.
        """
        try:
            ci = datetime.strptime(check_in, "%Y-%m-%d").date()
            co = datetime.strptime(check_out, "%Y-%m-%d").date()
        except:
            return {"error": "Datas em formato inválido. Use YYYY-MM-DD"}
        
        occupied_room_ids = db.query(models.Booking.room_id).filter(
            models.Booking.status.in_([models.BookingStatus.CONFIRMADO, models.BookingStatus.ATIVO]),
            models.Booking.check_out_date > ci,
            models.Booking.check_in_date < co,
        ).all()
        occupied_ids = [r[0] for r in occupied_room_ids]
        
        rooms = db.query(models.Room).filter(
            models.Room.id.notin_(occupied_ids),
            models.Room.status == models.RoomStatus.DISPONIVEL
        ).order_by(models.Room.max_capacity.desc()).all()
        
        # Busca modelo de precificação para rotular o retorno
        settings_rows = db.query(models.SystemSetting).all()
        settings_dict = {s.key: s.value for s in settings_rows}
        model = settings_dict.get("pousada_pricing_model", "per_person")
        price_unit = "por pessoa" if model == "per_person" else "valor fixo do quarto"
        
        total_cap = sum(r.max_capacity for r in rooms)
        
        return {
            "pousada_pricing_model": model,
            "pricing_description": f"Os preços abaixo são {price_unit}.",
            "total_available_capacity": total_cap,
            "rooms": [
                {
                    "id": r.id, 
                    "number": r.id, 
                    "type": r.type, 
                    "daily_rate": r.price_per_night, 
                    "price_label": f"R$ {r.price_per_night:.2f} {price_unit}",
                    "capacity": r.max_capacity,
                    "description": r.description or "Sem observações específicas."
                } for r in rooms
            ],
            "request_info": f"Hóspede pediu por {capacity} pessoas. Capacidade total disponível no período: {total_cap}."
        }

    @tool
    def register_guest(name: str, email: str, phone: str, document: str, birth_date: str, profession: str, 
                       cep: str, street: str, number: str, neighborhood: str, 
                       city: str, state: str, notes: str = None) -> dict:
        """Cadastra um novo hóspede no sistema com todos os dados do formulário."""
        print(f"DEBUG: Agente chamando register_guest para {name} (CPF: {document})")
        try:
            # Validação básica de CPF
            clean_cpf = "".join(filter(str.isdigit, document))
            if not clean_cpf:
                return {"error": "CPF/Documento é obrigatório para o cadastro."}

            # Verifica duplicidade de CPF
            existing_cpf = db.query(models.Guest).filter(models.Guest.document == clean_cpf).first()
            if existing_cpf:
                return {"error": "Já existe um hóspede cadastrado com este CPF.", "id": existing_cpf.id, "name": existing_cpf.name}

            # Verifica duplicidade de Email
            if email:
                existing_email = db.query(models.Guest).filter(models.Guest.email == email).first()
                if existing_email:
                    return {"error": f"O email '{email}' já está em uso por outro hóspede (CPF: {existing_email.document})."}

            # Conversão de data
            b_date = None
            if birth_date:
                try:
                    b_date = datetime.strptime(birth_date, "%Y-%m-%d").date()
                except:
                    pass

            new_guest = models.Guest(
                name=name, email=email, phone=phone, document=clean_cpf,
                birth_date=b_date, profession=profession,
                address_zip=cep, address_street=street,
                address_number=number, address_neighborhood=neighborhood,
                address_city=city, address_state=state,
                notes=notes
            )
            db.add(new_guest)
            db.commit()
            db.refresh(new_guest)
            print(f"DEBUG: Hóspede {new_guest.name} cadastrado com ID {new_guest.id}")
            return {"id": new_guest.id, "name": new_guest.name, "message": "Hóspede cadastrado com sucesso!"}
        except Exception as e:
            db.rollback()
            err_msg = f"Erro ao cadastrar hóspede: {str(e)}"
            print(f"DEBUG: {err_msg}")
            return {"error": err_msg}

    @tool
    def create_pending_booking(guest_id: int, room_id: str, check_in_date: str, check_out_date: str, check_in_time: str, check_out_time: str, companions: list) -> dict:
        """Cria uma nova reserva com status PENDENTE.
        IMPORTANTE: O parâmetro 'companions' deve listar APENAS os acompanhantes EXTRAS (não inclua o hóspede principal aqui).
        Use YYYY-MM-DD para datas e HH:MM para horários.
        """
        try:
            ci_date = datetime.strptime(check_in_date, "%Y-%m-%d").date()
            co_date = datetime.strptime(check_out_date, "%Y-%m-%d").date()
        except:
            return {"error": "Datas em formato inválido. Use YYYY-MM-DD"}
            
        # Agora o room_id JA É o número do quarto
        room = db.query(models.Room).filter(models.Room.id == str(room_id)).first()
        guest = db.query(models.Guest).filter((models.Guest.id == guest_id) | (models.Guest.document == str(guest_id))).first()
        
        if not room: return {"error": "Quarto não encontrado no banco de dados."}
        if not guest: return {"error": "Hóspede não encontrado."}
        
        days = calculate_daily_rates_count(ci_date, co_date, check_in_time, check_out_time)
        guest_age = 18
        if guest.birth_date:
            today = date.today()
            guest_age = today.year - guest.birth_date.year - ((today.month, today.day) < (guest.birth_date.month, guest.birth_date.day))
        
        ages = [guest_age] + [c.get('age', 18) for c in companions]
        settings_rows = db.query(models.SystemSetting).all()
        settings_dict = {s.key: s.value for s in settings_rows}
        pricing = calculate_reservation_total(room.price_per_night, days, ages, settings=settings_dict)
        
        booking = models.Booking(
            guest_id=guest_id, room_id=room_id, check_in_date=ci_date, check_out_date=co_date,
            check_in_time=check_in_time, check_out_time=check_out_time, total_guests=1 + len(companions),
            daily_rate=room.price_per_night, total_amount=pricing["total"],
            status=models.BookingStatus.PENDENTE, mode=models.BookingMode.NORMAL
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        
        for c in companions:
            db.add(models.Companion(booking_id=booking.id, name=c.get('name', ''), age=c.get('age', 18)))
        db.commit()
        
        return {
            "booking_id": booking.id, "guest": guest.name, "room": room.id,
            "period": f"{check_in_date} às {check_in_time} até {check_out_date} às {check_out_time}",
            "total": pricing["total"], "status": "PENDENTE"
        }

    @tool
    def update_booking_guest(booking_id: int, new_guest_id: int) -> dict:
        """Altera o hóspede de uma reserva existente. 
        Use se o hóspede disser que o nome na reserva está incorreto e ele for outra pessoa."""
        try:
            booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
            if not booking:
                return {"error": "Reserva não encontrada."}
                
            new_guest = db.query(models.Guest).filter(models.Guest.id == new_guest_id).first()
            if not new_guest:
                return {"error": "Novo hóspede não encontrado com o ID fornecido."}
                
            booking.guest_id = new_guest.id
            db.commit()
            return {"message": "Reserva atualizada com sucesso!", "new_guest_name": new_guest.name}
        except Exception as e:
            db.rollback()
            return {"error": f"Erro técnico ao atualizar: {str(e)}"}

    @tool
    def search_events(query: str = None) -> list:
        """Busca eventos no calendário regional (ex: Canção Nova, Hosana Brasil, PHN). 
        Use isso quando o hóspede mencionar um evento ou perguntar sobre a 'programação' da cidade.
        Retorna os nomes e as datas exatas dos eventos para que você possa sugerir reservas.
        """
        db_query = db.query(models.Event)
        if query:
            # Busca por nome similar
            db_query = db_query.filter(models.Event.name.ilike(f"%{query}%"))
        
        # Filtra eventos futuros ou que terminam hoje
        from datetime import date as dt_date
        events = db_query.filter(models.Event.end_date >= dt_date.today()).order_by(models.Event.start_date.asc()).limit(10).all()
        
        if not events:
            return [{"message": "Nenhum evento futuro localizado com este nome."}]
            
        return [
            {
                "name": e.name,
                "start_date": e.start_date.strftime("%Y-%m-%d"),
                "end_date": e.end_date.strftime("%Y-%m-%d"),
                "location": e.location,
                "description": e.description
            } for e in events
        ]

    tools = [get_current_context, find_guest_by_cpf, find_guests_by_name, check_availability, register_guest, create_pending_booking, update_booking_guest, search_events]
    llm_with_tools = llm.bind_tools(tools)

    # --- LANGGRAPH SETUP ---
    sys_msg = SystemMessage(content="""Você é o **Especialista em Atendimento e Reservas da Pousada System**, um recepcionista humano e supereficiente. Seu objetivo é guiar o hóspede pelo processo de reserva.

### SUA ROTINA DE ATENDIMENTO:
1. **Identificação & Boas-vinda**: Você é o anfitrião digital. Comece com uma recepção calorosa. Pergunte o CPF/Documento.
2. **Hóspede JÁ CADASTRADO**: Se 'find_guest_by_cpf' retornar os dados do hóspede (id, name, email, phone), ele JÁ ESTÁ no sistema.
   - **MUITO IMPORTANTE**: GUARDE o 'id' do hóspede. Você DEVE usar estritamente este 'id' ao chamar 'create_pending_booking'. NUNCA invente IDs falsos ou suponha o ID.
   - **NÃO peça Nome, Email, WhatsApp, Data de Nascimento ou Endereço novamente.** Esses dados já existem.
   - Cumprimente-o pelo nome: "Olá, [NOME]! Que bom ter você de volta."
   - Vá DIRETO para: "Para qual período deseja reservar? (Check-in, Check-out, e quantas pessoas?)"
3. **Hóspede NÃO CADASTRADO**: Se 'find_guest_by_cpf' retornar erro, ofereça IMEDIATAMENTE o link:
   `[📋 Completar meu Cadastro](/registrar?cpf=XXXX)` (substitua XXXX pelo CPF informado).
   - Explique que isso agiliza o processo.
   - **Fallback**: Se o hóspede preferir continuar no chat, colete os dados em 3 grupos rápidos:
     - Grupo 1: Nome, Email, WhatsApp.
     - Grupo 2: Data de Nascimento, Profissão.
     - Grupo 3: CEP, Cidade, Estado.
4. **CÁLCULO DE DATAS**: Seja preciso (ex: "hoje" dia 8, "amanhã por 2 dias" -> In: 09, Out: 11).
5. **Disponibilidade**: Use 'check_availability' com a capacidade correta e sugira quartos com preço.
6. **Voucher & Confirmação**: Apresente um resumo formatado e, após "de acordo", crie a reserva PENDENTE.
   - *REGRA*: O hóspede principal conta como 1. 'companions' é apenas para acompanhantes EXTRAS. Se for 1 pessoa, envie companions=[].
7. **Eventos e Calendário**: Use 'search_events' sempre que o hóspede falar sobre eventos, festas ou nomes como 'PHN', 'Hosana'.
   - Se ele perguntar "quando é o evento X?", procure e informe as datas.
   - Se ele disser "quero reserva para o evento X", procure o evento, pegue as datas e use-as para chamar 'check_availability' automaticamente.
8. **Gestão de Grupos e Caravanas**: Se o hóspede pedir para muitas pessoas (ex: 20 pessoas):
   - Chame 'check_availability' com a capacidade total.
   - Se nenhum quarto individual couber todo mundo, olhe para o `total_available_capacity`.
   - Se a capacidade total for suficiente, proponha dividir o grupo: "Temos espaço para os 20! Podemos usar o Quarto A (10 pessoas) e o Quarto B (10 pessoas)."
   - Explique que o check-in é individual por quarto ou centralizado conforme ele preferir.
9. **Explicação de Preços (Modelo de Diária)**: Sempre considere o `pricing_model_active` retornado por 'get_current_context'.
   - Se o modelo for **'per_person'**: Explique que o valor é individual: "A diária é de R$ X por pessoa."
   - **MUITO IMPORTANTE**: No modelo 'per_person', o preço da ferramenta é UNITÁRIO. Você DEVE multiplicar: `Valor * Hóspedes * Noites` para dar o total geral. Nunca mostre apenas o valor de 1 diária de quarto se houver 20 pessoas.
   - Se o modelo for **'per_room'**: Explique que o valor é pelo quarto: "A diária do quarto é R$ X, independente do número de pessoas."
10. **RECOMENDAÇÕES INTELIGENTES**:
    Ao listar quartos disponíveis (check_availability), analise SEMPRE o campo 'description'. 
    - Se o hóspede pedir algo específico (ex: 'perto do elevador', 'sem escadas', 'cama de casal', 'vista para o jardim'), prioritize quartos que mencionem isso na descrição.
    - Se o hóspede não pedir nada específico, mas a descrição tiver algo atrativo (ex: 'Quarto mais silencioso da pousada'), use isso para "vender" a ideia.
    - Sempre cite a característica que justifica sua recomendação. Ex: "Recomendo o quarto 101 pois ele fica no térreo, atendendo seu pedido de evitar escadas."

### REGRAS DE OURO:
- **MATEMÁTICA**: No modelo 'per_person', se há 20 pessoas e a diária é 100, o total de 3 noites é R$ 6.000,00. Faça a conta correta!
- **IDENTIDADE DO HÓSPEDE**: Ao criar uma reserva, utilize apenas o `guest_id` EXATO retornado pelas ferramentas de busca ou cadastro. Se ocorreu um erro no nome e o usuário reclamar, chame a ferramenta `update_booking_guest` para corrigir passando o ID correto.
- **NUNCA peça dados que a ferramenta já retornou.** Isso irrita o cliente.
- **Links**: Use Markdown para botões bonitos.
- **Tom**: Profissional, acolhedor e ágil.
- **Ação imediata**: Chame as ferramentas assim que tiver os dados. Nunca diga "um momento".
- **Inteligência de Datas**: Se o evento é de 10 a 13, sugira check-in no dia 10 e check-out no dia 13 (ou conforme a preferência).
""")

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
    # Aumentamos o histórico para 40 mensagens para suportar cadastros longos
    for h in history[-40:]:
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
        print(f"❌ Erro LangGraph no Agente Cliente: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"response": "Tive um problema técnico ao processar sua solicitação agora (Erro LangGraph). Pode repetir o que deseja?"}
