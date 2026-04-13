import os

class MercadoPagoUnavailable(Exception):
    pass

class MercadoPagoService:
    def __init__(self):
        try:
            try:
                import mercadopago as mp
                self.SDK = mp.SDK
            except Exception:
                from mercadopago import SDK  # type: ignore
                self.SDK = SDK
        except Exception as e:
            raise MercadoPagoUnavailable(f"Falha ao importar mercadopago: {e}")

    def _get_client(self, access_token: str):
        if not access_token:
            raise ValueError("Access Token do Mercado Pago é obrigatório.")
        return self.SDK(access_token.strip())

    def create_pix_payment(self, access_token: str, tenant_id: int, amount: float, description: str, metadata: dict, payer: dict | None = None):
        client = self._get_client(access_token)
        explicit = os.getenv("NOTIFICATION_URL")
        base = os.getenv("NGROK_URL", "http://127.0.0.1:8000")
        notification = (explicit or (base.rstrip("/") + "/payments/webhook"))
        env = (os.getenv("ENVIRONMENT") or "development").lower()
        
        # Injeta tenant_id no metadata se não existir
        full_metadata = metadata or {}
        full_metadata["tenant_id"] = tenant_id
        
        body = {
            "transaction_amount": float(amount),
            "description": description,
            "payment_method_id": "pix",
            "metadata": full_metadata,
            "external_reference": f"{tenant_id}:{full_metadata.get('booking_id', '0')}"
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
            
        result = client.payment().create(body)
        return result

    def create_card_preference(self, access_token: str, tenant_id: int, amount: float, title: str, metadata: dict, back_urls: dict | None = None):
        client = self._get_client(access_token)
        explicit = os.getenv("NOTIFICATION_URL")
        base = os.getenv("NGROK_URL", "http://127.0.0.1:8000")
        notification = (explicit or (base.rstrip("/") + "/payments/webhook"))
        
        full_metadata = metadata or {}
        full_metadata["tenant_id"] = tenant_id

        pref = {
            "items": [
                {
                    "title": title,
                    "quantity": 1,
                    "unit_price": float(amount)
                }
            ],
            "metadata": full_metadata,
            "auto_return": "approved",
            "external_reference": f"{tenant_id}:{full_metadata.get('booking_id', '0')}"
        }
        
        if back_urls:
            pref["back_urls"] = back_urls
        if notification.startswith("https://"):
            pref["notification_url"] = notification
            
        result = client.preference().create(pref)
        return result

    def get_payment(self, access_token: str, payment_id: int):
        client = self._get_client(access_token)
        result = client.payment().get(payment_id)
        return result

    def test_connection(self, access_token: str):
        """Tenta listar métodos de pagamento para validar o token"""
        try:
            client = self._get_client(access_token)
            # Uma chamada leve para verificar se o token é aceito
            result = client.payment_methods().list()
            status = result.get("status")
            if int(status) >= 400:
                print(f"[MP ERROR] test_connection: status={status} response={result.get('response')}")
            return int(status) < 400
        except Exception as e:
            print(f"[MP CRITICAL] test_connection exception: {e}")
            return False
