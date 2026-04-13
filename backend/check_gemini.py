import os
import google.generativeai as genai
from dotenv import load_dotenv

# Carrega o .env se existir
if os.path.exists(".env"):
    load_dotenv(".env")

api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("ERRO: GOOGLE_API_KEY não encontrada no ambiente.")
else:
    print(f"Chave detectada: {api_key[:10]}...")
    genai.configure(api_key=api_key)
    
    print("\n--- Modelos Disponíveis para sua Chave ---")
    try:
        models = genai.list_models()
        flash_models = [m.name for m in models if 'flash' in m.name.lower()]
        
        if not flash_models:
            print("Nenhum modelo 'Flash' localizado. Listando todos:")
            for m in genai.list_models():
                print(f"- {m.name}")
        else:
            for name in flash_models:
                print(f"- {name} (Use no .env: {name.replace('models/', '')})")
                
    except Exception as e:
        print(f"Erro ao consultar modelos: {e}")
