import json
import os
from typing import Optional, List, Any, Dict
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from database import SessionLocal, set_tenant_context
import models

class CustomerEngineV2:
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    # -------------------------------------------------------------------------
    # UTILS INTERNOS (SEM SHARED_TOOLS)
    # -------------------------------------------------------------------------
    def _parse_date(self, date_val: Any) -> Optional[date]:
        """Parser de data atômico e resiliente."""
        if not date_val: return None
        if isinstance(date_val, (date, datetime)):
            return date_val.date() if isinstance(date_val, datetime) else date_val
        
        date_str = str(date_val).strip()
        try:
            if "/" in date_str:
                parts = date_str.split("/")
                d = int(parts[0])
                m = int(parts[1])
                y = int(parts[2]) if len(parts) > 2 else datetime.now().year
                return date(y, m, d)
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except: return None

    # -------------------------------------------------------------------------
    # ROBÔ 1: IDENTIFICADOR (CPF / CADASTRO)
    # -------------------------------------------------------------------------
    async def robot_identify_guest(self, cpf: str, session_id: str = "") -> Dict[str, Any]:
        """
        Busca hóspede pelo CPF ou gera link de cadastro.
        """
        clean_cpf = "".join(filter(str.isdigit, cpf))
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5174")
        
        with SessionLocal() as db:
            set_tenant_context(db, self.tenant_id)
            guest = db.query(models.Guest).filter(models.Guest.document == clean_cpf).first()
            
            if guest:
                return {
                    "success": True,
                    "guest_id": guest.id,
                    "name": guest.name,
                    "message": f"Hóspede {guest.name} localizado com sucesso."
                }
            else:
                link = f"{frontend_url}/{self.tenant_id}/registrar?cpf={clean_cpf}&sid={session_id}"
                return {
                    "success": False,
                    "needs_registration": True,
                    "registration_link": link,
                    "message": "CPF não cadastrado. Link de registro gerado."
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
            
            # 1. Busca Quarto mais barato disponível (Econômico) e o mais caro (Premium)
            # Para cotação rápida, pegamos a média do tipo Standard se não houver ID específico
            rooms = db.query(models.Room).filter(models.Room.status == "disponivel").all()
            if not rooms: return {"success": False, "error": "Não há quartos disponíveis para estas datas."}
            
            # 2. Busca Eventos no período
            event = db.query(models.Event).filter(
                models.Event.start_date <= co,
                models.Event.end_date >= ci
            ).first()
            
            # 3. Busca Regras de Preço (FDS, etc)
            settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
            days = (co - ci).days
            if days <= 0: days = 1
            
            options = []
            for r in rooms[:3]: # Oferece até 3 opções
                base_price = r.price_per_night
                if event and event.daily_rate > 0:
                    base_price = event.daily_rate
                
                total = base_price * days * group_size
                options.append({
                    "room_id": r.id,
                    "type": r.type,
                    "total": total,
                    "daily": base_price
                })
            
            return {
                "success": True,
                "options": options,
                "days": days,
                "event": event.name if event else None,
                "message": f"Cotação para {days} diárias processada."
            }

    # -------------------------------------------------------------------------
    # ROBÔ 3: BUSCADOR DE QUARTOS (AVAILABILITY)
    # -------------------------------------------------------------------------
    async def robot_search_available_rooms(self, check_in: str, check_out: str, group_size: int) -> Dict[str, Any]:
        """
        Busca quartos específicos que comportam o grupo e estão livres.
        """
        ci = self._parse_date(check_in)
        co = self._parse_date(check_out)
        
        with SessionLocal() as db:
            set_tenant_context(db, self.tenant_id)
            
            # Subquery para achar quartos ocupados
            occupied_ids = db.query(models.Booking.room_id).filter(
                models.Booking.status.in_(["confirmado", "ativo", "pendente"]),
                models.Booking.check_out_date > ci,
                models.Booking.check_in_date < co
            ).all()
            occupied_list = [r[0] for r in occupied_ids]
            
            # Filtra quartos livres e com capacidade
            available = db.query(models.Room).filter(
                ~models.Room.id.in_(occupied_list),
                models.Room.max_capacity >= group_size,
                models.Room.status == "disponivel"
            ).all()
            
            if not available:
                return {"success": False, "message": "Nenhum quarto disponível com esta capacidade para estas datas."}
            
            return {
                "success": True,
                "rooms": [{"id": r.id, "type": r.type, "price": r.price_per_night, "floor": r.floor} for r in available]
            }

    # -------------------------------------------------------------------------
    # ROBÔ 4: CRIADOR DE RESERVA (ATÔMICO)
    # -------------------------------------------------------------------------
    async def robot_create_booking_atomic(self, guest_id: int, room_id: str, check_in: str, check_out: str, group_size: int) -> Dict[str, Any]:
        """
        Cria a reserva no banco de dados e retorna o ID e valor do sinal.
        """
        ci = self._parse_date(check_in)
        co = self._parse_date(check_out)
        
        with SessionLocal() as db:
            set_tenant_context(db, self.tenant_id)
            
            # 1. Validação Final de Disponibilidade (Lock)
            existing = db.query(models.Booking).filter(
                models.Booking.room_id == room_id,
                models.Booking.status.in_(["confirmado", "ativo", "pendente"]),
                models.Booking.check_out_date > ci,
                models.Booking.check_in_date < co
            ).first()
            
            if existing:
                return {"success": False, "error": "Este quarto acaba de ser ocupado. Por favor, escolha outro."}
            
            # 2. Busca Preço Real do Quarto
            room = db.query(models.Room).get(room_id)
            days = (co - ci).days
            total_amount = (room.price_per_night if room else 150) * days * group_size
            
            # 3. Cria a Reserva
            booking = models.Booking(
                tenant_id=self.tenant_id,
                guest_id=guest_id,
                room_id=room_id,
                check_in_date=ci,
                check_out_date=co,
                total_guests=group_size,
                total_amount=total_amount,
                status="pendente"
            )
            db.add(booking)
            db.commit()
            db.refresh(booking)
            
            # 4. Calcula Sinal (Down Payment)
            settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
            deposit_pct = float(settings.get("pousada_deposit_percentage", 50))
            down_payment = (total_amount * deposit_pct) / 100
            
            return {
                "success": True,
                "booking_id": booking.id,
                "total_amount": total_amount,
                "down_payment": down_payment,
                "message": f"Reserva #{booking.id} criada! Valor total R$ {total_amount:.2f}. Sinal: R$ {down_payment:.2f}"
            }

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
            
            settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
            pix_key = settings.get("pix_key_manual", "financeiro@pousada.com.br")
            
            # Simulação de Link MP (Poderia chamar API real aqui)
            mp_link = f"https://www.mercadopago.com.br/checkout/v1/redirect?pref_id=TEST-{booking.id}"
            
            return {
                "success": True,
                "payment_method": "PIX/MercadoPago",
                "pix_qr": "Simulado_QR_Code_Base64",
                "manual_key": pix_key,
                "total": booking.total_amount,
                "message": "Dados de pagamento gerados."
            }

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
