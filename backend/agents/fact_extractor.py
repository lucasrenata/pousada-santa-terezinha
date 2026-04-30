from typing import Dict, Any
import json
import os
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

class FactExtractorAgent:
    """
    EXTRATOR DE FATOS (CUSTOMER ONLY)
    Extrator cirúrgico: Se não tiver 100% de certeza, retorna null.
    """
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        google_key = os.getenv("GOOGLE_API_KEY")
        gemini_model = os.getenv("GEMINI_MODEL")
        if google_key and gemini_model:
            self.llm = ChatGoogleGenerativeAI(model=gemini_model, google_api_key=google_key, temperature=0)
        else:
            self.llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"), temperature=0)

    async def extract(self, message: str, current_context: Dict[str, Any]) -> Dict[str, Any]:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d (%A)")
        
        prompt = f"""
Você é um extrator de dados para um sistema de hotelaria no BRASIL.
DATA DE HOJE (REFERÊNCIA): {today}

Sua tarefa é extrair APENAS o que o usuário afirmou explicitamente.

CAMPOS:
- cpf: String de 11 dígitos. 
- check_in: Data YYYY-MM-DD.
- check_out: Data YYYY-MM-DD.
- group_size: Inteiro.

REGRAS DE EXTRAÇÃO BRASIL:
1. Formatos como "01 a 05/05" significam: check_in={datetime.now().year}-05-01, check_out={datetime.now().year}-05-05.
2. "Amanhã" ou "Próximo sábado" devem ser calculados com base na DATA DE HOJE ({today}).
3. Se o ano não for mencionado, assuma o ano atual ou o próximo se a data já passou.
4. NÃO ADIVINHE se não houver números ou referências temporais.
5. Responda APENAS o JSON puro.

Mensagem do Hóspede: "{message}"
"""
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            cleaned = response.content.strip().replace("```json", "").replace("```", "")
            data = json.loads(cleaned)
            # Remove campos nulos para não sobrescrever o contexto anterior com "vazio"
            return {k: v for k, v in data.items() if v is not None}
        except:
            return {}
