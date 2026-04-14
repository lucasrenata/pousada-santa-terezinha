import os
import google.generativeai as genai
from dotenv import load_dotenv

# Carrega a chave do .env local
load_dotenv("backend/.env")
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("ERRO: GOOGLE_API_KEY não encontrada no .env")
    exit(1)

genai.configure(api_key=api_key)

print("--- LISTANDO MODELOS DISPONÍVEIS PARA SUA CHAVE ---")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"ID: {m.name} | Display Name: {m.display_name}")
except Exception as e:
    print(f"Erro ao listar modelos: {e}")
