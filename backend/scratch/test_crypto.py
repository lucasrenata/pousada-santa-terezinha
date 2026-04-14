from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("ENCRYPTION_KEY")
print(f"Chave encontrada: '{key}' (Tamanho: {len(key) if key else 0})")

try:
    f = Fernet(key.encode())
    print("✅ Chave válida para Fernet!")
    token = "TEST_TOKEN_123"
    enc = f.encrypt(token.encode())
    dec = f.decrypt(enc).decode()
    print(f"✅ Teste de Criptografia: {token} -> {dec}")
except Exception as e:
    print(f"❌ Erro na Chave: {e}")
