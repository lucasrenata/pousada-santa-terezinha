import json
import os
import logging
from typing import Optional, List, Any, Dict
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, text
from database import SessionLocal, set_tenant_context
import models
from utils.pricing import calculate_reservation_total, calculate_daily_rates_count

logger = logging.getLogger("AI_ENGINE")

class CustomerEngineV2:
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    # -------------------------------------------------------------------------
    # UTILS INTERNOS
    # -------------------------------------------------------------------------
    def _parse_date(self, date_val: Any) -> Optional[date]:
        """Delega ao parser centralizado e flexível."""
        from utils.date_parser import parse_date
        return parse_date(date_val)

    # -------------------------------------------------------------------------
    # ROBÔ 1: IDENTIFICADOR (CPF / CADASTRO)
    # -------------------------------------------------------------------------
    async def robot_identify_guest(self, cpf: str, session_id: str = "") -> Dict[str, Any]:
        """
        Busca hóspede pelo CPF ou gera link de cadastro (com Instrumentação e Retry).
        """
        import asyncio
        
        clean_cpf = "".join(filter(str.isdigit, cpf))
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5174")
        
        logger.info(f"[ROBOT_ID] Iniciando busca por CPF: {clean_cpf} (Tenant: {self.tenant_id})")
        
        for attempt in range(3):
            with SessionLocal() as db:
                set_tenant_context(db, self.tenant_id)
                # Forçamos uma verificação do que o DB está "vendo" agora
                tid_check = db.execute(text("SHOW app.current_tenant")).scalar()
                logger.info(f"[ROBOT_ID] Tentativa {attempt+1}. Contexto RLS no DB: {tid_check}")
                
                guest = db.query(models.Guest).filter(models.Guest.document == clean_cpf).first()
                
                if guest:
                    logger.info(f"[ROBOT_ID] ✅ Sucesso! Hóspede encontrado: {guest.name} (ID: {guest.id})")
                    return {
                        "success": True,
                        "guest_id": guest.id,
                        "name": guest.name,
                        "message": f"Hóspede {guest.name} localizado com sucesso."
                    }
                else:
                    logger.warning(f"[ROBOT_ID] ⚠️ Hóspede não encontrado na tentativa {attempt+1}")
            
            if attempt < 2:
                await asyncio.sleep(2.0)
        
        # Garante que o session_id não seja a string "null"
        clean_sid = session_id if session_id and session_id != "null" else ""
        link = f"{frontend_url}/{self.tenant_id}/registrar?cpf={clean_cpf}&sid={clean_sid}".replace(" ", "")
        
        logger.info(f"[ROBOT_ID] Link gerado: {link}")
        return {
            "success": False,
            "needs_registration": True,
            "registration_link": link,
            "message": "Hóspede não localizado.",
            "script_hint": f"Informe que não localizou o cadastro e forneça o link de registro: {link}"
        }

    # -------------------------------------------------------------------------
    # ROBÔ 2: CONSULTOR DE PREÇOS (QUOTATION)
    # -------------------------------------------------------------------------
    async def robot_calculate_quote(self, check_in: str, check_out: str, group_size: int = 1) -> Dict[str, Any]:
        """
        Calcula o valor total da estadia considerando regras de negócio e eventos.
        """
        ci = self._parse_date(check_in)
        co = self._parse_date(check_out)
        if not ci or not co: return {"success": False, "error": "Datas inválidas."}

        with SessionLocal() as db:
            set_tenant_context(db, self.tenant_id)
            
            # Subquery para achar quartos ocupados ou reservados no período
            occupied_ids = db.query(models.Booking.room_id).filter(
                models.Booking.status.in_(["confirmado", "ativo", "pendente"]),
                models.Booking.check_out_date > ci,
                models.Booking.check_in_date < co
            ).all()
            occupied_list = [r[0] for r in occupied_ids]

            # Também verifica na tabela de associação multi-quarto
            multi_occupied = db.query(models.BookingRoom.room_id).join(models.Booking).filter(
                models.Booking.status.in_(["confirmado", "ativo", "pendente"]),
                models.Booking.check_out_date > ci,
                models.Booking.check_in_date < co
            ).all()
            occupied_list += [r[0] for r in multi_occupied]

            # Busca quartos que não estão ocupados no período e não estão em manutenção
            # Nota: Removido filtro rígido de capacidade para permitir sugestão de múltiplos quartos menores
            rooms = db.query(models.Room).filter(
                ~models.Room.id.in_(occupied_list),
                models.Room.status != "manutencao"
            ).order_by(models.Room.price_per_night.asc()).all()
            
            if not rooms: return {"success": False, "error": "Não há quartos disponíveis para estas datas."}
            
            # Busca Eventos no período
            event = db.query(models.Event).filter(
                models.Event.start_date <= co,
                models.Event.end_date >= ci
            ).first()
            
            days = (co - ci).days
            if days <= 0: days = 1
            
            # Busca Configurações para o Cálculo
            settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
            
            options = []
            seen_types = set()
            
            for r in rooms:
                if r.type not in seen_types:
                    seen_types.add(r.type)
                    
                    base_price = r.price_per_night
                    if event and event.daily_rate > 0:
                        base_price = event.daily_rate
                    
                    # Usa o motor oficial de cálculo (considera idades e modelo per_person/per_room)
                    # Se não temos as idades agora, assumimos adultos para a cotação inicial
                    ages_mock = [18] * group_size
                    calc = calculate_reservation_total(base_price, days, ages_mock, settings=settings)
                    
                    options.append({
                        "room_id": r.id,
                        "type": r.type,
                        "total": calc["total"],
                        "daily": base_price,
                        "pricing_model": calc.get("pricing_model")
                    })
                    
                if len(options) >= 3:
                    break
            
            # Preenche até 3 se houver poucas categorias diferentes
            if len(options) < 3:
                for r in rooms:
                    if not any(o['room_id'] == r.id for o in options):
                        base_price = r.price_per_night
                        if event and event.daily_rate > 0:
                            base_price = event.daily_rate
                        
                        calc = calculate_reservation_total(base_price, days, [18]*group_size, settings=settings)
                        options.append({
                            "room_id": r.id,
                            "type": r.type,
                            "total": calc["total"],
                            "daily": base_price,
                            "pricing_model": calc.get("pricing_model")
                        })
                        if len(options) >= 3:
                            break
            
            return {
                "success": True,
                "options": options,
                "days": days,
                "event": event.name if event else None,
                "message": f"Cotação para {days} diárias processada.",
                "script_hint": f"Apresente as opções de quartos disponíveis para {days} diárias e pergunte qual o hóspede prefere."
            }

    # -------------------------------------------------------------------------
    # ROBÔ 3: BUSCADOR DE QUARTOS (AVAILABILITY)
    # -------------------------------------------------------------------------
    async def robot_search_available_rooms(self, check_in: str, check_out: str, group_size: int = 1) -> Dict[str, Any]:
        """
        Busca quartos específicos que estão livres para o período.
        Nota: Removido filtro rígido de capacidade para permitir que a IA sugira múltiplos quartos.
        """
        ci = self._parse_date(check_in)
        co = self._parse_date(check_out)
        
        if not ci or not co:
            return {"success": False, "message": "Datas de check-in ou check-out inválidas."}

        with SessionLocal() as db:
            set_tenant_context(db, self.tenant_id)
            
            # Subquery para achar quartos ocupados ou reservados
            occupied_ids = db.query(models.Booking.room_id).filter(
                models.Booking.status.in_(["confirmado", "ativo", "pendente"]),
                models.Booking.check_out_date > ci,
                models.Booking.check_in_date < co
            ).all()
            occupied_list = [r[0] for r in occupied_ids]
            
            # Também verifica na tabela de associação multi-quarto
            multi_occupied = db.query(models.BookingRoom.room_id).join(models.Booking).filter(
                models.Booking.status.in_(["confirmado", "ativo", "pendente"]),
                models.Booking.check_out_date > ci,
                models.Booking.check_in_date < co
            ).all()
            occupied_list += [r[0] for r in multi_occupied]

            # Filtra quartos livres (não ocupados no período e não em manutenção)
            available = db.query(models.Room).filter(
                ~models.Room.id.in_(occupied_list),
                models.Room.status != "manutencao"
            ).all()
            
            if not available:
                return {"success": False, "message": "Nenhum quarto disponível para estas datas."}
            
            return {
                "success": True,
                "rooms": [{"id": r.id, "type": r.type, "price": r.price_per_night, "capacity": r.max_capacity, "floor": r.floor} for r in available],
                "instructions": "Se o grupo for maior que a capacidade de um quarto, sugira a reserva de múltiplos quartos."
            }

    # -------------------------------------------------------------------------
    # ROBÔ 4: CRIADOR DE RESERVA (ATÔMICO)
    # -------------------------------------------------------------------------
    async def robot_create_booking_atomic(self, guest_id: int, room_ids: Any, check_in: str, check_out: str, group_size: int, companions: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Cria a reserva no banco de dados para um ou mais quartos e retorna o ID e valor do sinal.
        `room_ids` pode ser uma string (ex: "101") ou uma lista/string separada por vírgula (ex: "101,102").
        """
        ci = self._parse_date(check_in)
        co = self._parse_date(check_out)
        
        # Normaliza room_ids para lista
        if isinstance(room_ids, str):
            rooms_list = [r.strip() for r in room_ids.split(",") if r.strip()]
        elif isinstance(room_ids, list):
            rooms_list = room_ids
        else:
            rooms_list = [str(room_ids)]

        with SessionLocal() as db:
            set_tenant_context(db, self.tenant_id)
            
            try:
                # 1. Validação Final de Disponibilidade para todos os quartos
                for r_id in rooms_list:
                    existing = db.query(models.Booking).filter(
                        or_(models.Booking.room_id == r_id, 
                            models.Booking.room_associations.any(models.BookingRoom.room_id == r_id)),
                        models.Booking.status.in_(["confirmado", "ativo", "pendente"]),
                        models.Booking.check_out_date > ci,
                        models.Booking.check_in_date < co
                    ).first()
                    
                    if existing:
                        return {"success": False, "error": f"O quarto {r_id} acaba de ser ocupado. Por favor, escolha outro."}
                    
                    # Verifica se o quarto entrou em manutenção
                    room_obj = db.query(models.Room).get(r_id)
                    if room_obj and room_obj.status == "manutencao":
                        return {"success": False, "error": f"O quarto {r_id} entrou em manutenção e não pode ser reservado no momento."}
                
                # 2. Busca Configurações e Calcula Preço Real
                settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
                pricing_model = settings.get("pousada_pricing_model", "per_person")
                
                # Resolve os objetos dos quartos
                rooms_objs = db.query(models.Room).filter(models.Room.id.in_(rooms_list)).all()
                if not rooms_objs:
                    return {"success": False, "error": "Nenhum dos quartos informados foi encontrado."}
                
                # Média das diárias dos quartos escolhidos (para base de cálculo se necessário)
                avg_daily_rate = sum([r.price_per_night for r in rooms_objs]) / len(rooms_objs)
                days = (co - ci).days
                if days <= 0: days = 1

                total_amount = 0.0
                if pricing_model == "per_room":
                    # Soma o valor individual de cada quarto pelas diárias
                    total_amount = sum([r.price_per_night for r in rooms_objs]) * days
                else:
                    # Lógica Per Person: Usa idades REAIS se disponíveis
                    guest = db.query(models.Guest).get(guest_id)
                    guest_age = guest.age if guest and guest.age else 18
                    
                    # Coleta idades dos acompanhantes informados
                    comp_ages = []
                    if companions:
                        comp_ages = [c.get("age", 18) for c in companions]
                    
                    # Se faltarem acompanhantes na lista mas o group_size for maior, completa com 18
                    missing_count = (group_size - 1) - len(comp_ages)
                    if missing_count > 0:
                        comp_ages.extend([18] * missing_count)
                    
                    ages = [guest_age] + comp_ages[:group_size-1] # Garante que não passe do group_size
                    
                    calc = calculate_reservation_total(avg_daily_rate, days, ages, settings=settings)
                    total_amount = calc["total"]
                
                # 3. Cria a Reserva Principal
                # O campo room_id da tabela bookings fica com o primeiro quarto (para compatibilidade legada)
                booking = models.Booking(
                    tenant_id=self.tenant_id,
                    guest_id=guest_id,
                    room_id=rooms_list[0],
                    check_in_date=ci,
                    check_out_date=co,
                    total_guests=group_size,
                    total_amount=total_amount,
                    daily_rate=avg_daily_rate,
                    status="pendente"
                )
                db.add(booking)
                db.flush() 
                
                # 4. Cria as associações Multi-Quarto
                for r_id in rooms_list:
                    assoc = models.BookingRoom(
                        tenant_id=self.tenant_id,
                        booking_id=booking.id,
                        room_id=r_id
                    )
                    db.add(assoc)
                
                # 4.1 Adiciona os acompanhantes no banco
                if companions:
                    for comp_data in companions:
                        new_comp = models.Companion(
                            booking_id=booking.id,
                            name=comp_data.get("name", "Acompanhante"),
                            age=comp_data.get("age", 18),
                            tenant_id=self.tenant_id
                        )
                        db.add(new_comp)
                
                # 5. Calcula Sinal (Down Payment)
                deposit_pct = float(settings.get("pousada_deposit_percentage", 50))
                down_payment = (total_amount * deposit_pct) / 100
                booking.deposit_amount = down_payment
                
                logger.info(f"[ENGINE][ATOMIC] Reserva Multi-Quarto #{booking.id} ({len(rooms_list)} quartos) criada.")
                db.commit()
                
                rooms_str = ", ".join(rooms_list)
                return {
                    "success": True,
                    "booking_id": booking.id,
                    "total_amount": total_amount,
                    "down_payment": down_payment,
                    "message": f"Reserva #{booking.id} criada nos quartos {rooms_str}! Valor total R$ {total_amount:.2f}. Sinal de {int(deposit_pct)}%: R$ {down_payment:.2f}"
                }
            except Exception as e:
                db.rollback()
                logger.error(f"[ENGINE][ERROR] Falha atômica ao criar reserva: {e}")
                import traceback
                traceback.print_exc()
                return {"success": False, "error": f"Erro interno ao processar reserva: {str(e)}"}

    # -------------------------------------------------------------------------
    # ROBÔ 5: GERADOR DE PAGAMENTO
    # -------------------------------------------------------------------------
    async def robot_get_payment_info(self, booking_id: int) -> Dict[str, Any]:
        """
        Gera o link de pagamento ou chave PIX.
        """
        with SessionLocal() as db:
            set_tenant_context(db, self.tenant_id)
            booking = db.query(models.Booking).get(booking_id)
            if not booking: return {"success": False, "error": "Reserva não encontrada."}
            
            # Busca credenciais e chave PIX manual do Tenant
            tenant_config = db.query(models.TenantConfig).filter(models.TenantConfig.tenant_id == self.tenant_id).first()
            
            has_mp = tenant_config and tenant_config.mp_access_token and tenant_config.mp_public_key
            manual_pix_key = tenant_config.manual_pix_key if tenant_config and tenant_config.manual_pix_key else "Chave PIX não configurada"
            
            # Tenta Mercado Pago (Circuit Breaker)
            if has_mp:
                try:
                    logger.info(f"[ENGINE][PAYMENT] Gerando link Mercado Pago real para reserva #{booking_id}")
                    from payments.mercadopago_service import MercadoPagoService
                    mp_service = MercadoPagoService()
                    
                    # Calcula o valor do sinal
                    settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
                    deposit_pct = float(settings.get("pousada_deposit_percentage", 50))
                    down_payment = (booking.total_amount * deposit_pct) / 100
                    
                    pref = mp_service.create_card_preference(
                        access_token=tenant_config.mp_access_token,
                        tenant_id=self.tenant_id,
                        amount=down_payment,
                        title=f"Sinal Reserva #{booking.id}",
                        metadata={"booking_id": booking.id}
                    )
                    
                    if pref.get("status") == 201:
                        mp_link = pref["response"]["init_point"]
                        return {
                            "success": True,
                            "payment_method": "MercadoPago",
                            "link": mp_link,
                            "manual_key": manual_pix_key,
                            "total": booking.total_amount,
                            "message": f"Link de pagamento gerado com sucesso: {mp_link}"
                        }
                    else:
                        raise Exception(f"Falha na criação da preferência MP: {pref.get('message')}")
                except Exception as e:
                    logger.warning(f"[ENGINE][PAYMENT] Falha no Gateway Mercado Pago: {e}. Acionando FALLBACK PIX.")
                    # Fallback imediato para PIX Manual em caso de erro na API
                    return {
                        "success": True,
                        "payment_method": "PIX Manual (FALLBACK)",
                        "link": "",
                        "manual_key": manual_pix_key,
                        "total": booking.total_amount,
                        "message": f"⚠️ Gateway instável. Por favor, use a chave PIX Manual: {manual_pix_key}"
                    }
            else:
                # Se MP não estiver configurado, vai direto para PIX Manual
                logger.info(f"[ENGINE][PAYMENT] MP não configurado. Entregando PIX Manual.")
                return {
                    "success": True,
                    "payment_method": "PIX Manual",
                    "link": "",
                    "manual_key": manual_pix_key,
                    "total": booking.total_amount,
                    "message": f"Chave PIX Manual: {manual_pix_key}"
                }

    async def robot_get_booking_details(self, booking_id: int) -> dict:
        """Busca os detalhes completos de uma reserva existente pelo seu ID (número da reserva)."""
        db = SessionLocal()
        try:
            set_tenant_context(db, self.tenant_id)
            booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
            if not booking:
                return {"success": False, "message": f"Reserva #{booking_id} não encontrada."}
            
            return {
                "success": True,
                "booking_id": booking.id,
                "guest_name": booking.guest.name if booking.guest else "Hóspede",
                "check_in": booking.check_in_date.strftime("%d/%m/%Y"),
                "check_out": booking.check_out_date.strftime("%d/%m/%Y"),
                "room": booking.room_id,
                "total": booking.total_amount,
                "status": booking.status,
                "message": f"Reserva #{booking_id} localizada para {booking.guest.name}. Check-in em {booking.check_in_date.strftime('%d/%m/%Y')}."
            }
        except Exception as e:
            logger.error(f"[ENGINE][CONSULTA] Erro ao buscar reserva #{booking_id}: {e}")
            return {"success": False, "message": str(e)}
        finally:
            db.close()

    # -------------------------------------------------------------------------
    # ROBÔ 6: NOTIFICADOR PROATIVO
    # -------------------------------------------------------------------------
    async def robot_notify_payment_success(self, booking_id: int) -> Dict[str, Any]:
        """
        Gatilho para a IA avisar o hóspede sobre o sucesso do pagamento.
        """
        return {
            "success": True,
            "event": "PAYMENT_CONFIRMED",
            "booking_id": booking_id,
            "message": "O pagamento foi confirmado! Por favor, dê as boas-vindas oficiais ao hóspede."
        }

    # -------------------------------------------------------------------------
    # ROBÔ 7: BUSINESS INTELLIGENCE (REGRAS E EVENTOS)
    # -------------------------------------------------------------------------
    async def robot_business_intelligence(self) -> Dict[str, Any]:
        """
        Fornece as regras de negócio, manual de operação e calendário de eventos.
        """
        with SessionLocal() as db:
            set_tenant_context(db, self.tenant_id)
            
            rules = db.query(models.BusinessRule).filter(models.BusinessRule.is_active == True).all()
            events = db.query(models.Event).filter(models.Event.start_date >= datetime.now()).all()
            settings = db.query(models.SystemSetting).all()
            
            manual = {s.key: s.value for s in settings}
            rules_list = [f"{r.name}: {r.description}" for r in rules]
            events_list = [f"{e.name} ({e.start_date.strftime('%d/%m')} a {e.end_date.strftime('%d/%m')})" for e in events]
            
            return {
                "success": True,
                "manual": manual,
                "rules": rules_list,
                "events": events_list,
                "message": "Inteligência operacional carregada."
            }

    async def robot_register_receipt_upload(self, booking_id: int) -> dict:
        """
        REGISTRO MANUAL/IA DE COMPROVANTE:
        Replica a lógica do roteador de reservas para quando a IA detecta o pagamento.
        Muda status para CONFIRMADO e adiciona a nota sistêmica no card.
        """
        db = SessionLocal()
        try:
            set_tenant_context(db, self.tenant_id)
            booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
            if not booking:
                return {"success": False, "message": "Reserva não encontrada."}
            
            # --- MESMA LÓGICA DO ROUTER/BOOKINGS.PY ---
            booking.status = models.BookingStatus.CONFIRMADO
            booking.payment_status = models.PaymentStatus.PARCIAL
            
            deposit_val = booking.deposit_amount or 0.0
            auto_note = f"\n[SISTEMA] Hóspede enviou comprovante de PIX (Sinal de R$ {deposit_val:.2f}). Conferir PIX e confirmar a reserva para o hóspede."
            
            if booking.notes:
                if "[SISTEMA]" not in booking.notes: # Evita duplicar
                    booking.notes += auto_note
            else:
                booking.notes = auto_note.strip()
            
            db.commit()
            logger.info(f"✅ [ENGINE][PAYMENT] Automação de comprovante (via IA) concluída para reserva #{booking_id}")
            return {
                "success": True, 
                "message": "Status atualizado e nota registrada no card.",
                "script_hint": "Confirme que você já registrou o envio no sistema e que a reserva agora está com o status CONFIRMADA no painel."
            }
        except Exception as e:
            db.rollback()
            logger.error(f"❌ [ENGINE][PAYMENT] Erro ao registrar comprovante via IA: {e}")
            return {"success": False, "message": str(e)}
        finally:
            db.close()

    async def get_ai_persona(self) -> str:
        """Busca a personalização de tom de voz e cumprimentos do banco."""
        with SessionLocal() as db:
            set_tenant_context(db, self.tenant_id)
            setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "ai_persona_customization").first()
            return setting.value if setting and setting.value else ""
