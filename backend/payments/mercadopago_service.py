import os

class MercadoPagoUnavailable(Exception):
    pass

class MercadoPagoService:
    def __init__(self):
        try:
            try:
                import mercadopago as mp
                SDK = mp.SDK
            except Exception:
                from mercadopago import SDK  # type: ignore
        except Exception as e:
            raise MercadoPagoUnavailable(f"Falha ao importar mercadopago: {e}")
        token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
        if not token:
            raise MercadoPagoUnavailable("MERCADOPAGO_ACCESS_TOKEN ausente")
        try:
            self.client = SDK(token)
        except Exception as e:
            raise MercadoPagoUnavailable(f"Falha ao inicializar SDK: {e}")

    def create_pix_payment(self, amount: float, description: str, metadata: dict, payer: dict | None = None):
        explicit = os.getenv("NOTIFICATION_URL")
        base = os.getenv("NGROK_URL", "http://127.0.0.1:8000")
        notification = (explicit or (base.rstrip("/") + "/payments/webhook"))
        env = (os.getenv("ENVIRONMENT") or "development").lower()
        body = {
            "transaction_amount": float(amount),
            "description": description,
            "payment_method_id": "pix",
            "metadata": metadata or {}
        }
        if payer:
            p = dict(payer)
            ident = p.get("identification") or {}
            num = (ident.get("number") or "").strip()
            if env != "production":
                if not num:
                    p["identification"] = {"type": "CPF", "number": "19119119100"}
                if not p.get("first_name"):
                    p["first_name"] = "Test"
                if not p.get("last_name"):
                    p["last_name"] = "User"
            body["payer"] = p
        else:
            email = os.getenv("TEST_PAYER_EMAIL")
            if email and env != "production":
                body["payer"] = {
                    "email": email,
                    "first_name": "Test",
                    "last_name": "User",
                    "identification": {"type": "CPF", "number": "19119119100"}
                }
        if notification.startswith("https://"):
            body["notification_url"] = notification
        result = self.client.payment().create(body)
        return result

    def create_card_preference(self, amount: float, title: str, metadata: dict, back_urls: dict | None = None):
        explicit = os.getenv("NOTIFICATION_URL")
        base = os.getenv("NGROK_URL", "http://127.0.0.1:8000")
        notification = (explicit or (base.rstrip("/") + "/payments/webhook"))
        pref = {
            "items": [
                {
                    "title": title,
                    "quantity": 1,
                    "unit_price": float(amount)
                }
            ],
            "metadata": metadata or {},
            "auto_return": "approved",
            "external_reference": str(metadata.get("booking_id") or metadata.get("room_id") or "checkout")
        }
        if back_urls:
            pref["back_urls"] = back_urls
        if notification.startswith("https://"):
            pref["notification_url"] = notification
        result = self.client.preference().create(pref)
        return result

    def get_payment(self, payment_id: int):
        result = self.client.payment().get(payment_id)
        return result

    def get_status(self, payment_id: int):
        data = self.get_payment(payment_id)
        resp = data.get("response", {})
        return resp.get("status")
