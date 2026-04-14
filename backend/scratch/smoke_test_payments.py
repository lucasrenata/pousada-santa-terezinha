import requests

def test_endpoint():
    url = "http://localhost:8003/payments/test-config"
    # Precisamos de um token de admin para passar pelo Depends(get_current_staff)
    # Como rodar teste de integração completo requer login, vamos apenas validar se a rota existe
    try:
        # Enviando sem token de auth deve dar 401
        resp = requests.post(url, json={"token": "TEST-TOKEN"})
        print(f"Status Code (esperado 401 sem login): {resp.status_code}")
        if resp.status_code == 401:
            print("✅ Rota protegida corretamente.")
        elif resp.status_code == 404:
            print("❌ Rota não encontrada.")
    except Exception as e:
        print(f"Erro ao conectar na API: {e}")

if __name__ == "__main__":
    test_endpoint()
