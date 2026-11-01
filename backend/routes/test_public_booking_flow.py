import pytest
import io
import os
from fastapi.testclient import TestClient
from main import app
from datetime import datetime, timedelta
import models
from database import SessionLocal, set_tenant_context

client = TestClient(app)

def test_full_public_booking_and_payment_flow():
    # 0. Setup: Ensure tenant 1 exists and has room 101 in the database for the test
    db = SessionLocal()
    try:
        set_tenant_context(db, -1) # bypass RLS to seed/setup
        tenant = db.query(models.Tenant).filter(models.Tenant.id == 1).first()
        if not tenant:
            tenant = models.Tenant(id=1, name="ParcerIA (Plataforma)", is_active=True)
            db.add(tenant)
            db.commit()

        room = db.query(models.Room).filter(models.Room.id == "101").first()
        if not room:
            room = models.Room(
                id="101",
                type="Standard",
                price_per_night=150.0,
                max_capacity=2,
                status=models.RoomStatus.DISPONIVEL,
                tenant_id=1
            )
            db.add(room)
            db.commit()
    finally:
        db.close()

    # 1. Lookup non-existent guest (should return 404)
    document_cpf = "99988877766"
    response = client.get(f"/guests/public/lookup?document={document_cpf}&tenant_id=1")
    assert response.status_code == 404

    # 2. Register guest via public registration endpoint
    guest_payload = {
        "name": "Integration Test Guest",
        "email": "test_integration_guest@example.com",
        "phone": "(11) 98765-4321",
        "document": document_cpf,
        "birth_date": "1995-05-15",
        "profession": "Software Engineer",
        "address_zip": "01001-000",
        "address_street": "Praça da Sé",
        "address_number": "123",
        "address_neighborhood": "Sé",
        "address_city": "São Paulo",
        "address_state": "SP",
        "tenant_id": 1,
        "session_id": "test_session_abc"
    }
    response = client.post("/guests/public", json=guest_payload)
    assert response.status_code == 200
    guest_data = response.json()
    assert guest_data["name"] == "Integration Test Guest"
    assert guest_data["document"] == document_cpf

    # 3. Lookup the newly registered guest (should return 200)
    response = client.get(f"/guests/public/lookup?document={document_cpf}&tenant_id=1")
    assert response.status_code == 200
    assert response.json()["name"] == "Integration Test Guest"

    # 4. Create a public booking request
    check_in_date = (datetime.now() + timedelta(days=5)).isoformat()
    check_out_date = (datetime.now() + timedelta(days=7)).isoformat()

    booking_payload = {
        "tenant_id": 1,
        "guest": {
            "name": "Integration Test Guest",
            "email": "test_integration_guest@example.com",
            "phone": "(11) 98765-4321",
            "document": document_cpf,
            "birth_date": "1995-05-15",
            "profession": "Software Engineer",
            "address_zip": "01001-000",
            "address_street": "Praça da Sé",
            "address_number": "123",
            "address_neighborhood": "Sé",
            "address_city": "São Paulo",
            "address_state": "SP"
        },
        "room_id": "101",
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "check_in_time": "14:00",
        "check_out_time": "14:00",
        "mode": "normal",
        "total_guests": 1,
        "daily_rate": 150.0,
        "notes": "Testing integration public booking creation.",
        "companions": []
    }
    response = client.post("/bookings/public", json=booking_payload)
    assert response.status_code == 200
    booking_res = response.json()
    assert booking_res["message"] == "Solicitação recebida!"
    booking_id = booking_res["booking_id"]
    assert booking_id is not None

    # 5. Upload a mock payment receipt for the booking
    dummy_file = io.BytesIO(b"dummy pix receipt content")
    response = client.post(
        f"/bookings/{booking_id}/receipt?tenant_id=1",
        files={"file": ("receipt.png", dummy_file, "image/png")}
    )
    assert response.status_code == 200
    receipt_res = response.json()
    assert receipt_res["success"] is True
    assert "receipt_url" in receipt_res

    # Cleanup created test data to avoid polluting the database
    db = SessionLocal()
    try:
        set_tenant_context(db, -1)
        # Delete receipt file if exists
        booking_obj = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
        if booking_obj and booking_obj.payment_receipt_url:
            file_path = booking_obj.payment_receipt_url.lstrip("/")
            if os.path.exists(file_path):
                os.remove(file_path)

        db.query(models.Companion).filter(models.Companion.booking_id == booking_id).delete()
        db.query(models.Booking).filter(models.Booking.id == booking_id).delete()
        db.query(models.Guest).filter(models.Guest.document == document_cpf).delete()
        db.commit()
    except Exception as e:
        print(f"Error clean up: {e}")
    finally:
        db.close()
