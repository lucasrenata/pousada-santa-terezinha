import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from agents.state_manager import StateManager
from database import SessionLocal

class ReviewerAgent:
    """
    AGENTE REVISOR (O COACH)
    Atua em paralelo revisando o Quadro Negro e o Histórico.
    Sua missão é garantir que a IA principal não seja burra ou repetitiva.
    """
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name, 
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0
        )

    async def review_and_update_blackboard(self, session_id: str, last_message: str, history: list):
        sm = StateManager(self.tenant_id)
        blackboard = sm.get_context(session_id)
        
        # 1. Monta o contexto para a revisão
        history_text = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in history[-5:]])
        
        prompt = f"""
Você é um Supervisor de Atendimento de Pousada. Sua função é analisar o histórico e o Quadro Negro (estado atual) e dar uma instrução CURTA e DIRETA para o atendente.

QUADRO NEGRO ATUAL:
{blackboard}

ÚLTIMAS MENSAGENS:
{history_text}
Hóspede: {last_message}

MISSÃO:
- Identifique se o hóspede já forneceu algum dado (CPF, datas, quantidade de pessoas).
- Se o atendente estiver prestes a perguntar algo que já sabemos, PROÍBA.
- Se o hóspede mudou de assunto, oriente a responder e voltar ao roteiro.

Sua resposta deve ser apenas a instrução para o atendente (Coach Note). Seja rígido.
Exemplo: "O hóspede já informou o CPF. Pule para a pergunta sobre acompanhantes."
"""
        
        try:
            # Gemini prefere HumanMessage para chamadas diretas ou lista com System+Human
            messages = [
                SystemMessage(content="Você é um Supervisor de Atendimento de Pousada."),
                HumanMessage(content=prompt)
            ]
            response = await self.llm.ainvoke(messages)
            coach_note = response.content
            
            # 2. Atualiza o Quadro Negro com a instrução do Coach
            sm.update_state(session_id, {"coach_note": coach_note})
            return coach_note
        except Exception as e:
            print(f"[REVIEWER_ERROR] Falha na revisão: {e}")
            return None
