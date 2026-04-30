"""
Simulação completa do fluxo de atendimento — do olá até a chave PIX.
Testa todos os Sub-Agentes em sequência real.
"""
import asyncio
import sys
import json
import uuid

sys.path.insert(0, '/app')

from database import SessionLocal, set_tenant_context
import models

# ─── CONFIG ────────────────────────────────────────────────────────────────────
TENANT_ID = 1
SESSION_ID = f"sim_full_{uuid.uuid4().hex[:8]}"

# ─── UTILITÁRIOS ────────────────────────────────────────────────────────────────
def separator(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")

def print_response(agent: str, response: str):
    agent_label = {
        "faq_agent": "🔵 FAQ",
        "reservas_agent": "🟡 RESERVAS",
        "pagamento_agent": "🟢 PAGAMENTO",
    }.get(agent, "🤖 ANA")
    print(f"\n{agent_label}: {response}\n")

async def send_message(message: str, turn: int):
    """Envia uma mensagem pelo SupervisorAgent e retorna o resultado."""
    from agents.supervisor_agent import SupervisorAgent
    separator(f"TURNO {turn} — Hóspede: \"{message}\"")
    supervisor = SupervisorAgent(TENANT_ID)
    result = await supervisor.process(message, SESSION_ID)
    print_response(result.get("agent", "?"), result.get("response", "[SEM RESPOSTA]"))
    return result

async def check_db_state():
    """Exibe o estado persistido da sessão após cada turno."""
    from agents.state_manager import StateManager
    sm = StateManager(TENANT_ID)
    ctx = sm.get_context(SESSION_ID)
    if ctx:
        print(f"  📋 Estado persistido:")
        for k, v in ctx.items():
            if v and v != [] and v != {}:
                val = json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                print(f"     {k}: {val}")

async def get_real_guest_id() -> int:
    """Busca um hóspede real do banco para usar no teste."""
    with SessionLocal() as db:
        set_tenant_context(db, TENANT_ID)
        guest = db.query(models.Guest).first()
        if guest:
            return guest.id, guest.document, guest.name
    return None, None, None

async def check_pix_config():
    """Verifica a chave PIX configurada no TenantConfig."""
    with SessionLocal() as db:
        set_tenant_context(db, TENANT_ID)
        cfg = db.query(models.TenantConfig).filter(
            models.TenantConfig.tenant_id == TENANT_ID
        ).first()
        if cfg:
            print(f"  💳 MercadoPago configurado: {'SIM' if cfg.mp_access_token else 'NÃO'}")
            print(f"  🔑 Chave PIX manual: {cfg.manual_pix_key or 'NÃO CONFIGURADA'}")
            return cfg.manual_pix_key
        else:
            print("  ⚠️  TenantConfig não encontrado para tenant 1!")
            return None

# ─── FLUXO PRINCIPAL ────────────────────────────────────────────────────────────
async def main():
    print("\n" + "="*60)
    print("  SIMULAÇÃO COMPLETA — FLUXO DO ATENDIMENTO")
    print("="*60)
    print(f"  Tenant: {TENANT_ID} | Sessão: {SESSION_ID}")

    # Pré-verificações
    separator("PRÉ-VERIFICAÇÕES DO BANCO")
    guest_id, guest_cpf, guest_name = await get_real_guest_id()
    if guest_id:
        print(f"  ✅ Hóspede encontrado: {guest_name} (CPF: {guest_cpf})")
    else:
        print("  ❌ Nenhum hóspede cadastrado no banco!")
        print("     Criando hóspede de teste...")
        with SessionLocal() as db:
            set_tenant_context(db, TENANT_ID)
            guest = models.Guest(
                name="Maria Silva Teste",
                document="11122233344",
                email="maria@teste.com",
                phone="11999887766",
                tenant_id=TENANT_ID
            )
            db.add(guest)
            db.commit()
            db.refresh(guest)
            guest_id = guest.id
            guest_cpf = guest.document
            guest_name = guest.name
            print(f"  ✅ Hóspede criado: {guest_name} (CPF: {guest_cpf})")

    pix_key = await check_pix_config()

    # ─── SIMULAÇÃO ──────────────────────────────────────────────────────────────
    try:
        # Turno 1: Saudação
        await send_message("Olá! Quero fazer uma reserva.", 1)
        await check_db_state()

        # Turno 2: Informa datas e grupo
        await send_message("Quero de 05/06/2027 até 07/06/2027 para 2 pessoas.", 2)
        await check_db_state()

        # Turno 3: Escolhe o quarto (assumindo que o agente listou opções)
        await send_message("Quero o quarto mais barato disponível.", 3)
        await check_db_state()

        # Turno 4: Informa CPF
        await send_message(f"Meu CPF é {guest_cpf}.", 4)
        await check_db_state()

        # Turno 5: Informa acompanhante (se group_size > 1)
        await send_message("O acompanhante é Carlos, 28 anos.", 5)
        await check_db_state()

        # Turno 6: Confirma reserva
        await send_message("Sim, pode confirmar a reserva!", 6)
        await check_db_state()

        # Turno 7: Pagamento (Novo teste)
        result = await send_message("Qual a chave pix para o pagamento?", 7)
        await check_db_state()

        # ─── VERIFICAÇÃO FINAL ──────────────────────────────────────────────────
        separator("VERIFICAÇÃO FINAL")
        response = result.get("response", "")
        agent = result.get("agent", "")

        print(f"  Agente que respondeu: {agent}")

        checks = {
            "Agente de Pagamento ativo": agent == "pagamento_agent",
            "Chave PIX na resposta": pix_key and pix_key in response,
            "Nenhuma chave inventada": "pousada.encantada" not in response and "ficticia" not in response.lower(),
            "Sem link do MP inventado": "mercadopago.com" not in response or "TEST-" in response,
            "Tem número de reserva": any(c.isdigit() for c in response),
        }

        print()
        all_pass = True
        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            if not passed:
                all_pass = False
            print(f"  {status} {check}")

        print()
        if all_pass:
            print("  🎉 SUCESSO TOTAL — Fluxo completo sem alucinações!")
        else:
            print("  ⚠️  Alguns checks falharam. Verifique os logs acima.")

        # Verifica booking no banco
        from agents.state_manager import StateManager
        sm = StateManager(TENANT_ID)
        ctx = sm.get_context(SESSION_ID)
        booking_id = ctx.get("booking_id")
        if booking_id:
            with SessionLocal() as db:
                set_tenant_context(db, TENANT_ID)
                booking = db.query(models.Booking).get(booking_id)
                if booking:
                    print(f"\n  📦 Reserva #{booking_id} no banco:")
                    print(f"     Status: {booking.status}")
                    print(f"     Total: R$ {booking.total_amount:.2f}")
                    print(f"     Quarto: {booking.room_id}")
        else:
            print("\n  ⚠️  Booking_id não encontrado no estado persistido.")
            print("      O agente de pagamento pode não ter sido acionado nesta sessão.")

    except Exception as e:
        import traceback
        print(f"\n❌ ERRO NA SIMULAÇÃO: {e}")
        traceback.print_exc()

    # Limpeza
    separator("LIMPEZA DA SESSÃO DE TESTE")
    with SessionLocal() as db:
        set_tenant_context(db, TENANT_ID)
        
        # Limpa mensagens
        msgs = db.query(models.ChatMessage).filter(
            models.ChatMessage.session_id == SESSION_ID
        ).all()
        for m in msgs:
            db.delete(m)
            
        # Limpa estado da sessão
        st = db.query(models.SessionState).filter(
            models.SessionState.session_id == SESSION_ID
        ).first()
        if st:
            db.delete(st)
            
        db.commit()
        print(f"  🗑️  Histórico e estado da sessão {SESSION_ID} removidos.")

if __name__ == "__main__":
    asyncio.run(main())
