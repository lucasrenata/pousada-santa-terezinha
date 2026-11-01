import requests
import io

BASE_URL = "http://localhost:8000"
TENANT_ID = 1
CPF = "11122233344"

def run_flow():
    print("1. Buscando hóspede pelo CPF...")
    resp = requests.get(f"{BASE_URL}/guests/public/lookup?document={CPF}&tenant_id={TENANT_ID}")
    if resp.status_code == 200:
        print("Hóspede já cadastrado!")
        guest = resp.json()
    else:
        print("Hóspede não cadastrado, realizando cadastro...")
        guest_payload = {
            "name": "Hospede Validacao API",
            "email": "hospede_validacao@example.com",
            "phone": "(11) 98888-7777",
            "document": CPF,
            "birth_date": "1990-01-01",
            "profession": "Validador",
            "address_zip": "12345-678",
            "address_street": "Rua da Validacao",
            "address_number": "42",
            "address_neighborhood": "Centro",
            "address_city": "Aparecida",
            "address_state": "SP",
            "tenant_id": TENANT_ID,
            "session_id": "validation_session"
        }
        resp = requests.post(f"{BASE_URL}/guests/public", json=guest_payload)
        assert resp.status_code == 200, f"Erro no cadastro: {resp.text}"
        guest = resp.json()
        print(f"Hóspede cadastrado com ID: {guest['id']}")

    print("\n2. Criando solicitação de reserva pública...")
    booking_payload = {
        "tenant_id": TENANT_ID,
        "guest": {
            "name": guest["name"],
            "email": guest["email"],
            "phone": guest["phone"],
            "document": guest["document"],
            "birth_date": guest["birth_date"],
            "profession": guest["profession"],
            "address_zip": guest["address_zip"],
            "address_street": guest["address_street"],
            "address_number": guest["address_number"],
            "address_neighborhood": guest["address_neighborhood"],
            "address_city": guest["address_city"],
            "address_state": guest["address_state"]
        },
        "room_id": "101",
        "check_in_date": "2026-08-01T14:00:00",
        "check_out_date": "2026-08-05T12:00:00",
        "check_in_time": "14:00",
        "check_out_time": "12:00",
        "mode": "normal",
        "total_guests": 1,
        "daily_rate": 150.0,
        "notes": "Criada pelo fluxo de validacao de API.",
        "companions": []
    }
    resp = requests.post(f"{BASE_URL}/bookings/public", json=booking_payload)
    assert resp.status_code == 200, f"Erro na reserva: {resp.text}"
    booking_res = resp.json()
    booking_id = booking_res["booking_id"]
    print(f"Reserva criada com ID: {booking_id}")

    print("\n3. Enviando foto fictícia como comprovante...")
    # Cria bytes simulando imagem PNG do comprovante
    dummy_image = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    file_payload = {
        "file": ("pix_receipt.png", io.BytesIO(dummy_image), "image/png")
    }
    resp = requests.post(f"{BASE_URL}/bookings/{booking_id}/receipt?tenant_id={TENANT_ID}", files=file_payload)
    assert resp.status_code == 200, f"Erro no upload: {resp.text}"
    receipt_res = resp.json()
    print(f"Comprovante enviado com sucesso! URL: {receipt_res['receipt_url']}")

    # Consulta banco para verificar se o status foi atualizado para CONFIRMADO
    print("\n4. Consultando o estado final da reserva no banco...")
    from database import SessionLocal, set_tenant_context
    import models
    db = SessionLocal()
    try:
        set_tenant_context(db, -1)
        booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
        print(f"--- DETALHES DA RESERVA #{booking.id} ---")
        print(f"Status da Reserva: {booking.status}")
        print(f"Status do Pagamento: {booking.payment_status}")
        print(f"Comprovante URL: {booking.payment_receipt_url}")
        print(f"Notas: {booking.notes}")
        print("-----------------------------------------")
    finally:
        db.close()

if __name__ == "__main__":
    run_flow()
