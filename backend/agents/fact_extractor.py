import logging
import json
from datetime import datetime
from typing import Dict, Any
from agents.base_specialist import BaseSpecialist

logger = logging.getLogger(__name__)

class FactExtractorAgent(BaseSpecialist):
    """
    Agente ultra-leve que roda em paralelo para extrair fatos
    estruturados de qualquer mensagem do usuário, independente do estado.
    """
    
    def __init__(self, tenant_id: int):
        # Nome único para logs
        super().__init__(tenant_id, "FACT_EXTRACTOR")

    async def extract(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analisa a mensagem em busca de fatos críticos.
        """
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d (%A)")
            current_year = now.year
            
            # Prompt focado em JSON estruturado
            prompt = f"""
            Você é um Extrator de Fatos para um sistema de pousada.
            HOJE É: {today_str}. O ANO ATUAL É {current_year}.
            
            Sua missão é extrair dados estruturados da mensagem.
            
            REGRAS DE OURO:
            - Se o usuário disser "dia 20 e 21/04" ou "abril", use o ANO ATUAL ({current_year}).
            - Se o usuário disser "amanhã", calcule com base em {today_str}.
            - Se o usuário mudar uma data ou o número de pessoas (ex: "mudei de ideia", "na verdade quero..."), capture os NOVOS valores.
            - Caso o usuário mencione um período (ex: "de 10 a 15"), extraia check_in e check_out.
            - Retorne APENAS o JSON.
            
            EXTREMA IMPORTÂNCIA:
            - Se o usuário disser "vou sozinho", o group_size é 1 e companions é [].
            - Se o usuário disser "eu e minha esposa", o group_size é 2.
            
            Fatos a extrair:
            - check_in (YYYY-MM-DD)
            - check_out (YYYY-MM-DD)
            - group_size (inteiro)
            - room_id (string ou lista de strings se for Smart Split)
            - cpf (somente números)
            - guest_name (nome do hóspede principal)
            - mudei_de_ideia (booleano - true se o usuário explicitamente alterou dados anteriores)
            - companions (lista de objetos JSON com 'name' e 'age'. Ex: [{{"name": "Ana", "age": 30}}])
            
            Mensagem: "{message}"
            Contexto Anterior: {json.dumps(context, ensure_ascii=False)}
            """
            
            # Usamos o self.llm da BaseSpecialist (LangChain)
            response = await self.llm.ainvoke(prompt)
            content = response.content.strip()
            
            # Limpeza de markdown de código se houver
            if content.startswith("```"):
                content = content.replace("```json", "").replace("```", "").strip()
            
            # LOG DE DEBUG CRÍTICO
            logger.info(f"[FACT_EXTRACTOR] Resposta bruta: {content}")
            
            facts = json.loads(content)
            if facts:
                logger.info(f"[FACT_EXTRACTOR] Fatos capturados: {facts}")
            return facts
            
        except Exception as e:
            logger.error(f"[FACT_EXTRACTOR] Erro na extração rápida: {str(e)}")
            return {}
