from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

load_dotenv()

class CryptoService:
    def __init__(self):
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            raise ValueError("ENCRYPTION_KEY não configurada no ambiente (.env)")
        self.fernet = Fernet(key.encode())

    def encrypt_token(self, token: str) -> str:
        """Criptografa o token e retorna uma string base64"""
        if not token:
            return ""
        encrypted_bytes = self.fernet.encrypt(token.encode())
        return encrypted_bytes.decode()

    def decrypt_token(self, encrypted_token: str) -> str:
        """Descriptografa o token e retorna a string original"""
        if not encrypted_token:
            return ""
        decrypted_bytes = self.fernet.decrypt(encrypted_token.encode())
        return decrypted_bytes.decode()
