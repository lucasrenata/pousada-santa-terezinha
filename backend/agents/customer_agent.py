import json
import os
from sqlalchemy.orm import Session
import models
from database import set_tenant_context
from utils.pricing import calculate_daily_rates_count, calculate_reservation_total
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

async def handle_customer_query(message: str, history: list, db: Session, tenant_id: int, base_url: str = ""):
    llm = get_llm()
    if not llm:
        return {"response": "A chave da OpenAI não foi configurada. Por favor, adicione sua API Key no arquivo .env."}

    # =========================================================================
    # MICRO-ROBÔS FOCADOS EM TAREFAS
    # =========================================================================
    
    @tool
    def robot_availability_checker(check_in: str, check_out: str, group_size: int = 1) -> dict:
        """
        Verifica quartos disponíveis, calcula a capacidade e reporta eventos e restrições.
        Use SEMPRE que o cliente perguntar "tem vaga?", "qual o preço?", "quais os quartos?".
        Datas devem ser no formato YYYY-MM-DD.
        """
        try:
            set_tenant_context(db, tenant_id)
            ci = datetime.strptime(check_in, "%Y-%m-%d").date()
            co = datetime.strptime(check_out, "%Y-%m-%d").date()
            
            event = db.query(models.Event).filter(models.Event.start_date <= co, models.Event.end_date >= ci).first()
            days = calculate_daily_rates_count(ci, co, "14:00", "14:00")
            settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
            active_rules = db.query(models.BusinessRule).filter(models.BusinessRule.is_active == True).all()
            
            occupied = [r[0] for r in db.query(models.Booking.room_id).filter(
                models.Booking.status.in_([models.BookingStatus.CONFIRMADO, models.BookingStatus.ATIVO]),
                models.Booking.check_out_date > ci,
                models.Booking.check_in_date < co
            ).all()]
            
            rooms = db.query(models.Room).filter(models.Room.id.notin_(occupied), models.Room.status != models.RoomStatus.MANUTENCAO).all()
            
            final_rooms = []
            for r in rooms:
                allowed = True
                couple_rule = next((rule for rule in active_rules if rule.name == "Restrição de Casal"), None)
                if couple_rule and group_size == 2:
                    restricted_rooms = [rid.strip() for rid in couple_rule.config.get("room_ids", "").split(",") if rid.strip()]
                    if r.id in restricted_rooms:
                        has_weekend = any((ci + timedelta(days=i)).weekday() in [4, 5, 6] for i in range(days))
                        if has_weekend:
                            allowed = False
                if allowed:
                    final_rooms.append(r)

            return {
                "available_rooms": [{"id": r.id, "cap": r.max_capacity, "price": r.price_per_night} for r in final_rooms],
                "event_info": getattr(event, "name", "Nenhum evento") if event else "Nenhum evento",
                "total_capacity_available": sum(r.max_capacity for r in final_rooms),
                "pricing_model": settings.get("pousada_pricing_model", "per_person"),
                "rules_active": [r.name for r in active_rules]
            }
        except Exception as e:
            db.rollback()
            return {"error": f"Erro técnico na verificação de disponibilidade: {str(e)}"}

    # Tool robot_get_registration_link removida em prol de uma arquitetura combinada na find_guest
    @tool
    def robot_family_reservation(
        guest_id: int, room_id: str, check_in: str, check_out: str, companions: List[dict], check_in_time: str = "14:00", check_out_time: str = "14:00"
    ) -> dict:
        """
        Cria uma reserva FAMILIAR ou de AMIGOS para 1 único quarto (Até 6 pessoas).
        Você OBRIGATORIAMENTE precisa passar a lista de companions (ex: [{"name":"Maria", "age":35}]).
        """
        try:
            set_tenant_context(db, tenant_id)
            ci = datetime.strptime(check_in, "%Y-%m-%d").date()
            co = datetime.strptime(check_out, "%Y-%m-%d").date()
        except:
            return {"error": "Datas obrigatórias no formato YYYY-MM-DD."}
            
        group_size = 1 + len(companions)
        guest = db.query(models.Guest).get(guest_id)
        if not guest: return {"error": "Hóspede não encontrado."}
        
        if len(companions) < (group_size - 1):
            return {"error": f"Faltam dados dos acompanhantes. Preciso do nome e idade dos {group_size - 1} extras."}
        for c in companions:
            if not c.get("name") or str(c.get("age", "")) == "":
                return {"error": "Cada acompanhante deve ter nome e idade informados."}

        event = db.query(models.Event).filter(models.Event.start_date <= co, models.Event.end_date >= ci).first()
        days = calculate_daily_rates_count(ci, co, check_in_time, check_out_time)
        settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
        active_rules = db.query(models.BusinessRule).filter(models.BusinessRule.is_active == True).all()

        total_amount = 0.0
        daily_rate_label = ""
        
        if event and (event.daily_rate_single > 0 or event.daily_rate_couple > 0):
            adults = 1 + len([c for c in companions if int(c.get('age', 18)) >= 13])
            children = len([c for c in companions if 7 <= int(c.get('age', 0)) < 13])
            if adults == 1 and event.daily_rate_single > 0:
                total_amount = (event.daily_rate_single + (children * event.daily_rate_child)) * days
                daily_rate_label = f"Tarifa Solteiro Evento: R${event.daily_rate_single}"
            elif adults >= 2 and event.daily_rate_couple > 0:
                extras = adults - 2
                total_amount = (event.daily_rate_couple + (extras * event.daily_rate_extra) + (children * event.daily_rate_child)) * days
                daily_rate_label = f"Tarifa Casal Evento: R${event.daily_rate_couple}"
            else:
                daily_rate = event.daily_rate or 100.0
                g_age = 18
                if getattr(guest, "birth_date", None):
                    today = date.today()
                    bd = guest.birth_date
                    g_age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
                ages = [g_age] + [int(c.get('age', 18)) for c in companions]
                pricing = calculate_reservation_total(daily_rate, days, ages, settings=settings)
                total_amount = pricing["total"]
                daily_rate_label = f"Tarifa Especial Evento: R${daily_rate}/pessoa"
        else:
            room = db.query(models.Room).get(room_id)
            daily_rate = room.price_per_night if room else 100.0
            g_age = 18
            if getattr(guest, "birth_date", None):
                today = date.today()
                bd = guest.birth_date
                g_age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
            ages = [g_age] + [int(c.get('age', 18)) for c in companions]
            pricing = calculate_reservation_total(daily_rate, days, ages, settings=settings)
            total_amount = pricing["total"]
            daily_rate_label = f"Tarifa Padrão: R${daily_rate}"

        final_total = total_amount
        multiplier_label = ""
        
        fds_rule = next((rule for rule in active_rules if rule.name == "Tarifa Fim de Semana"), None)
        if fds_rule:
            has_weekend = any((ci + timedelta(days=i)).weekday() in [4, 5, 6] for i in range(days))
            if has_weekend:
                mult = float(fds_rule.config.get("multiplier", 1.0))
                final_total *= mult
                multiplier_label += f" | Ajuste FDS (x{mult})"

        long_rule = next((rule for rule in active_rules if rule.name == "Desconto Estadia Longa"), None)
        if long_rule:
            min_d = int(long_rule.config.get("min_days", 999))
            if days >= min_d:
                disc = float(long_rule.config.get("discount_percent", 0)) / 100.0
                final_total *= (1 - disc)
                multiplier_label += f" | Desc. Longa Estadia (-{disc*100}%)"

        try:
            booking = models.Booking(
                guest_id=guest_id, room_id=room_id, check_in_date=ci, check_out_date=co,
                check_in_time=check_in_time, check_out_time=check_out_time,
                total_guests=group_size, daily_rate=0.0, total_amount=final_total, 
                mode=models.BookingMode.NORMAL, status=models.BookingStatus.PENDENTE,
                notes=f"{daily_rate_label}{multiplier_label}"
            )
            db.add(booking)
            db.commit()
            db.refresh(booking)
            for c in companions:
                age_val = int(c.get('age', 18)) if str(c.get('age', '')).isdigit() else 18
                db.add(models.Companion(booking_id=booking.id, name=c['name'], age=age_val))
            db.commit()
            return {"success": True, "booking_id": booking.id, "total": final_total, "type": "FAMILIA", "label": f"{daily_rate_label}{multiplier_label}"}
        except Exception as e:
            db.rollback()
            return {"error": f"Erro técnico ao gerar reserva: {str(e)}"}

    @tool
    def robot_caravan_organizer(
        guest_id: int, check_in: str, check_out: str, group_size: int, check_in_time: str = "14:00", check_out_time: str = "14:00"
    ) -> dict:
        """
        Organiza e cria EXCURSÕES / CARAVANAS. Distribuindo as pessoas (ex: 45) pela capacidade dos quartos disponíveis!
        O robô varre os quartos de maior capacidade e cria os SubBookings dinamicamente para comportar o grupo.
        Você SÓ precisa solicitar a Quantidade Total de Pessoas e o CPF do LÍDER!
        """
        try:
            set_tenant_context(db, tenant_id)
            ci = datetime.strptime(check_in, "%Y-%m-%d").date()
            co = datetime.strptime(check_out, "%Y-%m-%d").date()
        except:
            return {"error": "Datas obrigatórias no formato YYYY-MM-DD."}
            
        guest = db.query(models.Guest).get(guest_id)
        if not guest: return {"error": "Líder da caravana (Hóspede) não encontrado."}
        
        event = db.query(models.Event).filter(models.Event.start_date <= co, models.Event.end_date >= ci).first()
        if not event or event.daily_rate <= 0:
            return {"error": "Reservas de Caravana exigem um Evento / Pacote cadastrado com tarifa por pessoa."}
            
        days = calculate_daily_rates_count(ci, co, check_in_time, check_out_time)
        daily_rate = event.daily_rate

        occupied = [r[0] for r in db.query(models.Booking.room_id).filter(
            models.Booking.status.in_([models.BookingStatus.CONFIRMADO, models.BookingStatus.ATIVO]),
            models.Booking.check_out_date > ci,
            models.Booking.check_in_date < co
        ).all()]
        
        available_rooms = db.query(models.Room).filter(
            models.Room.id.notin_(occupied),
            models.Room.status != models.RoomStatus.MANUTENCAO
        ).order_by(models.Room.max_capacity.desc()).all()
        
        target_rooms = []
        current_cap = 0
        for r in available_rooms:
            target_rooms.append(r)
            current_cap += r.max_capacity
            if current_cap >= group_size:
                break
        
        if current_cap < group_size:
            return {"error": f"Capacidade insuficiente. Apenas {current_cap} vagas disponíveis, mas a caravana é de {group_size} pessoas."}

        try:
            total_amount_global = daily_rate * group_size * days
            amount_per_room = total_amount_global / len(target_rooms) if target_rooms else 0
            
            main_booking_id = None
            for r in target_rooms:
                b = models.Booking(
                    guest_id=guest_id, room_id=r.id, check_in_date=ci, check_out_date=co,
                    check_in_time=check_in_time, check_out_time=check_out_time,
                    total_guests=group_size, daily_rate=daily_rate, total_amount=amount_per_room,
                    mode=models.BookingMode.CARAVANA, status=models.BookingStatus.PENDENTE,
                    notes=f"Líder da Caravana: {guest.name}. Distribuição Alocada dinamicamente pelo Robô. (Vaga total selecionada: {current_cap})"
                )
                db.add(b)
                db.commit()
                db.refresh(b)
                if not main_booking_id: main_booking_id = b.id
            
            return {
                "success": True, 
                "leader_booking_id": main_booking_id, 
                "total": total_amount_global, 
                "rooms_blocked": len(target_rooms), 
                "total_capacity_reserved": current_cap,
                "type": "CARAVANA"
            }
        except Exception as e:
            db.rollback()
            return {"error": f"Erro ao organizar caravana: {str(e)}"}

    @tool
    def robot_generate_payment_qr(booking_id: int) -> dict:
        """
        Gera o QR Code PIX IMEDIATAMENTE após criar uma reserva para o cliente efetivar o pagamento.
        Recebe o ID da reserva que a sua ferramenta de criação (robot_family_reservation/robot_caravan_organizer) acabou de gerar.
        """
        try:
            set_tenant_context(db, tenant_id)
            booking = db.query(models.Booking).get(booking_id)
            if not booking:
                return {"error": "Reserva não encontrada."}
            
            # Import blocks restritos para evitar loops circulares no boot
            from routers.payments import get_tenant_mp_token
            from payments.mercadopago_service import MercadoPagoService
            import os
            
            try:
                token = get_tenant_mp_token(db, tenant_id)
                mp = MercadoPagoService()
            except Exception as e:
                return {"error": "O sistema de pagamento está indisponível ou desconfigurado no momento."}
                
            metadata = {"booking_id": booking.id, "type": "public", "tenant_id": tenant_id}
            description = f"Pagamento Confirmação - Reserva #{booking.id}"
            
            # Formatação do Pagador (Payer)
            payer = None
            guest = booking.guest
            if guest:
                from routers.payments import _cpf_digits, _cpf_valid
                cpf = _cpf_digits(guest.document or "")
                env = (os.getenv("ENVIRONMENT") or "development").lower()
                cpf = cpf if _cpf_valid(cpf) else "19119119100"
                full = (guest.name or "").strip()
                parts = [p for p in full.split() if p]
                first = parts[0] if parts else "Hóspede"
                last = parts[-1] if len(parts) > 1 else "Visitante"
                payer = {
                    "email": guest.email or "guest@test.com",
                    "first_name": first,
                    "last_name": last,
                    "identification": {"type": "CPF", "number": cpf}
                }
                
            result = mp.create_pix_payment(token, tenant_id, booking.total_amount, description, metadata, payer=payer)
            response = result.get("response") or {}
            status_code = result.get("status")

            if status_code and int(status_code) >= 400:
                print(f"[MP ERROR CHAT] status={status_code} error={response.get('error')}")
                return {"error": "O Mercado Pago recusou a emissão do PIX no momento. Avise o cliente."}
                
            poi = (response.get("point_of_interaction") or {}).get("transaction_data") or {}
            qr_base64 = poi.get("qr_code_base64")
            qr_code = poi.get("qr_code")
            
            if not qr_base64:
                return {"error": "Falha na decodificação do QR Code pelo banco. Avise a recepção."}
                
            return {
                "success": True,
                "instructions": "Envie o QR Code em formato de IMAGEM Markdown e o texto Copia-e-Cola abaixo. Diga que a reserva está PENDENTE e confirmará automaticamente ao pagar.",
                "qr_code_image_markdown": f"![QR Code PIX](data:image/png;base64,{qr_base64})",
                "copia_e_cola": f"`{qr_code}`"
            }
        except Exception as e:
            db.rollback()
            return {"error": f"Erro interno financeiro: {str(e)}"}

    # Mantemos ferramentas de busca para o fluxo de identificação
    @tool
    def find_guest(cpf: str = "", name: str = "") -> dict:
        """Busca hóspede por CPF ou Nome. Retorna o ID."""
        try:
            set_tenant_context(db, tenant_id)
            if cpf:
                clean_cpf = "".join(filter(str.isdigit, cpf))
                g = db.query(models.Guest).filter(models.Guest.document == clean_cpf).first()
                if g: return {"id": g.id, "name": g.name, "cpf": g.document}
            if name:
                gs = db.query(models.Guest).filter(models.Guest.name.ilike(f"%{name}%")).all()
                return {"results": [{"id": x.id, "name": x.name} for x in gs]}
            prefix = base_url.rstrip("/") if base_url else ""
            link_to_send = f"{prefix}/{tenant_id}/registrar?cpf={clean_cpf if cpf else ''}"
            return {
                "error": "Nenhum hóspede localizado.",
                "registration_instructions": "O cliente não tem cadastro e a reserva NÃO PODE PROSSEGUIR. Envie EXATAMENTE o link a seguir (Copiando e colando letra por letra sem modificar NADA, NEM O DOMINIO. NUNCA USE example.com). Diga para o cliente clicar, preencher a ficha e voltar ao chat.",
                "link_intocavel": link_to_send
            }
        except Exception as e:
            db.rollback()
            return {"error": f"Erro técnico ao buscar hópede: {str(e)}"}

    tools = [robot_availability_checker, robot_family_reservation, robot_caravan_organizer, robot_generate_payment_qr, find_guest]
    llm_with_tools = llm.bind_tools(tools)

    sys_msg = SystemMessage(content="""Você é o Especialista de Reservas da Pousada.
Sua missão é conduzir o hóspede até a reserva de ponta a ponta.

DIRETRIZES DE FLUXO (Siga a Ordem):
1. **IDENTIFICAÇÃO**: Peça sempre o CPF. Use `find_guest`.
2. **CADASTRO**: Se o `find_guest` não localizar, ele vai retornar um "link_intocavel". É ESTRITAMENTE PROIBIDO alterar o domínio ou usar example.com. Repasse EXATAMENTE o `link_intocavel` que a ferramenta lhe deu em formato markdown para o cliente preencher a ficha. Exemplo: `[Ficha de Cadastro](LINK_INTOCAVEL)`. Quando terminar, diga para clicar no botão de voltar para o chat e avisar "Pronto!".
3. **PESQUISA**: Se o cliente quer saber preços e vagas, use o `robot_availability_checker`.
4. **CHAMADA DE RESERVA**:
   - Família/Amigos/Casal (2 a 6 pessoas): Use o `robot_family_reservation`. Você DEVE pedir nome e idade de TODOS OS ACOMPANHANTES antes de chamar a ferramenta! (O guest_id vem do find_guest)
   - Excursão/Grupo Grande/Caravana (+15 pessoas): Use o `robot_caravan_organizer`. Não precisa de nomes, apenas de 'Quantas pessoas ao todo?' As vagas serão organizadas nos quartos dinamicamente baseando-se na capacidade deles.
5. **CONFIRMAÇÃO & PAGAMENTO**: Assim que qualquer ferramenta de Reserva retornar Sucesso e o ID da reserva, você NÃO DEVE dizer que a reserva está confirmada! Diga que a reserva está **PENDENTE** de pagamento. Em seguida (na mesma rodada ou assim que gerar a reserva), use a ferramenta `robot_generate_payment_qr(booking_id)` mandando o ID para gerar a fatura.
   Exiba ao hóspede o QR Code (`qr_code_image_markdown`) e o pix Copia-e-Cola (`copia_e_cola`) exatamente como instruído pela ferramenta. O webhook do sistema fará a confirmação em tempo real.
6. **RESPOSTA FINAL**: Seja gentil, use emojis, relate o sucesso claramente e avise se alguma regra de negócio alterou o valor final. Se relatar erros, não exiba o código feio, apenas seja simpático.
""")

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

    # History Transformation
    lc_messages = []
    for h in history[-20:]:
        role = h.get("role", "user")
        if role == "user": lc_messages.append(HumanMessage(content=h.get("content", "")))
        elif role == "assistant": lc_messages.append(AIMessage(content=h.get("content", "")))
    lc_messages.append(HumanMessage(content=message))

    try:
        final_state = await app.ainvoke({"messages": lc_messages})
        return {"response": final_state["messages"][-1].content}
    except Exception as e:
        db.rollback() # Garantia de que a transação não ficará "abortada" no banco
        import traceback
        traceback.print_exc()
        return {"response": "Desculpe, tive um erro técnico ao processar sua solicitação. Vamos tentar de novo?"}
