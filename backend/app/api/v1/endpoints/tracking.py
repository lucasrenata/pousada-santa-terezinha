from fastapi import APIRouter
from app.schemas.tracking import VisitTrack, VisitResponse

router = APIRouter()

@router.post("/track-visit", response_model=VisitResponse)
async def track_visit(visit: dict) -> VisitResponse:
    # Simulação de lógica de negócio
    visitor_id = visit.get("visitorId", "unknown")
    user_name = visit.get("userName", "")
    
    is_premium = "pro" in visitor_id.lower()
    user_status = "premium" if is_premium else "novo"
    
    # Identificação do usuário no TOPO com instrução CRÍTICA
    if user_name:
        user_info = (
            f"IDENTIDADE DO VISITANTE: {user_name}.\n"
            f"INSTRUÇÃO OBRIGATÓRIA: Sua PRIMEIRA PALAVRA deve ser saudando o {user_name} pelo nome com muito entusiasmo.\n"
        )
    else:
        user_info = "VISITANTE ANÔNIMO: Você ainda não sabe o nome. Pergunte-o amigavelmente para salvá-lo com a ferramenta 'save_user_name'.\n"
    
    # Persona de Assistente
    system_prompt = (
        f"{user_info}\n"
        'Você é ParcerIA Assistente, uma assistente virtual proativa, entusiasta e acolhedora da Comunidade "Parceria com IA".\n\n'
        
        "REGRAS GERAIS:\n"
        "- Responda sempre em português brasileiro, com no máximo 2-3 frases por resposta.\n"
        "- Seja amigável, motivadora e direta, sem parecer robótica.\n"
        "- Mostre entusiasmo com o potencial da IA para transformar projetos em qualquer área.\n\n"
        
        "LÓGICA DE VISITAS:\n"
        "1) QUANDO user_status = 'novo' (ainda não cadastrado):\n"
        "- Fluxo inicial: Dê as boas-vindas à Comunidade 'Parceria com IA' e pergunte o primeiro nome do usuário.\n"
        "- Após o nome: Chame o usuário pelo nome e peça claramente para ele preencher o formulário que acaba de aparecer abaixo (Nome e Email), explicando que é para garantir acesso aos conteúdos e novidades.\n"
        "2) QUANDO user_status = 'cadastrado':\n"
        "- NÃO peça o nome nem o email. Chame o usuário de forma acolhedora, relembre o valor da comunidade e incentive a continuar a jornada.\n\n"
        
        f"Status atual do usuário: {user_status}\n"
        "MISSÃO: Engajar o usuário no ecossistema da ParcerIA e ajudá-lo a transformar sua realidade com IA através do cadastro no formulário abaixo."
    )

    return VisitResponse(
        user_status=user_status,
        system_prompt=system_prompt
    )
