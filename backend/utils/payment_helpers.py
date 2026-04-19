import os
import models

def _cpf_digits(doc: str) -> str:
    return "".join([c for c in (doc or "") if c.isdigit()])

def _cpf_valid(doc: str) -> bool:
    s = _cpf_digits(doc)
    if len(s) != 11 or s == s[0] * 11:
        return False
    nums = [int(x) for x in s]
    sm = sum(nums[i] * (10 - i) for i in range(9))
    d1 = (sm * 10) % 11
    d1 = 0 if d1 == 10 else d1
    if d1 != nums[9]:
        return False
    sm = sum(nums[i] * (11 - i) for i in range(10))
    d2 = (sm * 10) % 11
    d2 = 0 if d2 == 10 else d2
    return d2 == nums[10]

def prepare_payer_data(guest: models.Guest):
    """Prepara o dicionário de pagador seguindo as regras de ambiente."""
    env = (os.getenv("ENVIRONMENT") or "development").lower()
    if not guest:
        return None
        
    full = (guest.name or "").strip()
    parts = [p for p in full.split() if p]
    first = parts[0] if parts else "Hóspede"
    last = parts[-1] if len(parts) > 1 else "S/S"
    
    cpf = _cpf_digits(guest.document or "")
    # Em produção, CPF inválido barra a criação (rejeitado pelo MP)
    if env == "production":
        if not _cpf_valid(cpf):
            return None # Sinaliza que não pode prosseguir
    else:
        # Em sandbox, injeta CPF de teste se o do hóspede for inválido
        cpf = cpf if _cpf_valid(cpf) else "19119119100"
        
    email = guest.email
    if env != "production":
        email = email or os.getenv("TEST_PAYER_EMAIL") or "guest@test.com"
    elif not email:
        email = "contato@pousada.com" # Fallback mínimo para produção

    return {
        "email": email,
        "first_name": first,
        "last_name": last,
        "identification": {"type": "CPF", "number": cpf}
    }

def process_mp_response(result: dict):
    """Processa a resposta bruta do MP para o formato padrão do sistema."""
    status_code = result.get("status")
    response = result.get("response") or {}
    
    if status_code and int(status_code) >= 400:
        error = {
            "error": response.get("error"),
            "message": response.get("message"),
            "cause": response.get("cause"),
        }
        print(f"[MP ERROR] API Status={status_code} Error={error}")
        return {
            "payment_id": None,
            "status": "failed",
            "api_status": status_code,
            "error": error
        }
    
    poi = (response.get("point_of_interaction") or {}).get("transaction_data") or {}
    
    # Extração robusta da URL de pagamento (vários fallbacks dependendo do tipo de resposta)
    payment_url = (
        poi.get("ticket_url") or 
        poi.get("external_resource_url") or 
        response.get("init_point") or 
        response.get("sandbox_init_point")
    )
    
    return {
        "payment_id": response.get("id"),
        "status": response.get("status"),
        "amount": response.get("transaction_amount"),
        "qr_code": poi.get("qr_code"),
        "qr_code_base64": poi.get("qr_code_base64"),
        "payment_url": payment_url,
        "metadata": response.get("metadata", {})
    }
