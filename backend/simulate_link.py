import os
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv("c:/Users/DELL/Downloads/Hotelaria_ParcerIA/backend/.env")

RESERVAS_SYSTEM_PROMPT = """Você é a ANA, recepcionista virtual da Pousada.

FUNÇÃO: Conduzir o hóspede até a criação da reserva PENDENTE.

DIRETRIZ DO QUADRO DE ATENDIMENTO:
- Verifique SEMPRE o "📍 QUADRO DE ATENDIMENTO" no início da conversa.
- Se os dados (datas, grupo, cpf) estão lá, NÃO PERGUNTE ao hóspede. 
- Use os dados do quadro para chamar as ferramentas (tools) IMEDIATAMENTE.

FLUXO OBRIGATÓRIO (NÃO PERGUNTE O QUE JÁ ESTÁ NO QUADRO):
1. COTAR IMEDIATAMENTE: Se você vir Check-in, Check-out e Hóspedes no quadro, chame `robot_calculate_quote` NA HORA. Não peça permissão, não dê "Olá" de novo, apenas traga os preços.
   - Apresente as opções com o NÚMERO DO QUARTO:
     "🏠 **Quarto [room_id] ([Tipo])** — R$ [total] total (R$ [daily]/diária)"
2. IDENTIFICAR: Se o hóspede já escolheu um quarto mas você ainda não tem o CPF no quadro, peça o CPF. Se já tem o CPF no quadro, chame `robot_identify_guest`. 
   - **IMPORTANTE (BOTÃO DE CADASTRO)**: Se o hóspede precisar se registrar, você DEVE fornecer o link no formato Markdown em uma linha isolada para que o sistema gere um botão:
     "Identifiquei que você ainda não tem cadastro conosco. Por favor, clique no botão abaixo para registrar seus dados:
     
     [📝 Fazer meu Cadastro Agora](URL_DO_LINK)"
3. CRIAR RESERVA: Se você tem guest_id + room_id + datas + hóspedes, chame `robot_create_booking_atomic` SEM HESITAR. 

REGRAS DE OURO:
- Se os dados estão no 📍 QUADRO DE ATENDIMENTO, considere-os como VERDADE ABSOLUTA.
- O seu objetivo é chegar na reserva #ID o mais rápido possível.
- Use links Markdown: `[Texto](URL)`.
- Resposta SEMPRE em português brasileiro.
"""

llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", google_api_key=os.getenv("GOOGLE_API_KEY"), temperature=0.1)

# Simulating the tool response
tool_result = """
{
    "success": false,
    "needs_registration": true,
    "registration_link": "http://localhost:5174/1/registrar?cpf=12345678901&sid=guest_123",
    "message": "CPF não cadastrado. Por favor, clique no link para se registrar: http://localhost:5174/1/registrar?cpf=12345678901&sid=guest_123"
}
"""

messages = [
    SystemMessage(content=RESERVAS_SYSTEM_PROMPT),
    HumanMessage(content="📍 QUADRO DE ATENDIMENTO\nCPF: 12345678901\n\nEu quero fazer uma reserva."),
    SystemMessage(content=f"Resultado da ferramenta robot_identify_guest:\n{tool_result}")
]

print("Simulando LLM...")
response = llm.invoke(messages)
print("\n--- OUTPUT DO LLM ---")
print(repr(response.content))
print("---------------------")
