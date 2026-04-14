import os
import mercadopago

class MercadoPagoUnavailable(Exception):
    pass

class MercadoPagoService:
    def __init__(self):
        pass

    def _get_sdk(self, access_token: str):
        return mercadopago.SDK(access_token)

    def test_connection(self, access_token: str) -> bool:
        try:
            sdk = self._get_sdk(access_token)
            result = sdk.payment_methods().list_all()
            return result.get("status") == 200
        except Exception as e:
            print(f"[MP CONNECTION TEST ERROR] {e}")
            return False

    def create_pix_payment(
        self,
        access_token: str,
        tenant_id: int,
        amount: float,
        description: str,
        metadata: dict,
        payer: dict = None
    ) -> dict:
        sdk = self._get_sdk(access_token)
        
        payment_data = {
            "transaction_amount": float(amount),
            "description": description,
            "payment_method_id": "pix",
            "external_reference": f"{tenant_id}:{metadata.get('booking_id', 0)}",
            "metadata": metadata,
            "notification_url": os.getenv("NOTIFICATION_URL", ""),
        }
        
        if payer:
            payment_data["payer"] = payer
        else:
            # Payer mínimo para ambiente de testes
            payment_data["payer"] = {
                "email": f"tenant_{tenant_id}@parceria.test"
            }
        
        result = sdk.payment().create(payment_data)
        return result

    def create_card_preference(
        self,
        access_token: str,
        tenant_id: int,
        amount: float,
        title: str,
        metadata: dict,
        back_urls: dict = None,
    ) -> dict:
        sdk = self._get_sdk(access_token)

        preference_data = {
            "items": [
                {
                    "title": title,
                    "quantity": 1,
                    "unit_price": float(amount),
                    "currency_id": "BRL",
                }
            ],
            "external_reference": f"{tenant_id}:{metadata.get('booking_id', 0)}",
            "metadata": metadata,
            "notification_url": os.getenv("NOTIFICATION_URL", ""),
        }

        if back_urls:
            preference_data["back_urls"] = back_urls
            preference_data["auto_return"] = "approved"

        result = sdk.preference().create(preference_data)
        return result

    def get_payment(self, access_token: str, payment_id: int) -> dict:
        sdk = self._get_sdk(access_token)
        return sdk.payment().get(payment_id)

    def get_status(self, payment_id: int) -> str:
        token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
        if not token:
            return "unavailable"
        try:
            sdk = self._get_sdk(token)
            result = sdk.payment().get(payment_id)
            response = result.get("response") or {}
            return response.get("status", "unknown")
        except Exception as e:
            print(f"[MP GET STATUS ERROR] {e}")
            return "error"
