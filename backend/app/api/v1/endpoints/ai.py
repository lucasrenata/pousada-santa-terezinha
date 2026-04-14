"""Rotas de IA (Chat Co-Professor)."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

from app.api.deps import get_current_active_user
from app.models.user import User
from app.services import ai_service

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    context: dict # Expects { "lesson_id": "...", "course_title": "..." }

@router.post("/chat")
async def ai_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Endpoint de chat do Co-Professor com STREAMING. 
    Retorna um StreamingResponse usando o formato SSE (data: ...\n\n).
    """
    
    if not current_user.ai_api_key or not current_user.ai_provider or not current_user.ai_model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Por favor, configure sua chave de API nas Configurações da plataforma para usar o Co-Professor IA."
        )

    lesson_id = request.context.get("lesson_id", "")
    course_title = request.context.get("course_title", "Curso")
    lesson_context = f"ID da Aula: {lesson_id}"

    async def stream_generator():
        try:
            async for chunk in ai_service.generate_ai_response_stream(
                message=request.message,
                course_title=course_title,
                lesson_context=lesson_context,
                ai_provider=current_user.ai_provider,
                ai_model=current_user.ai_model,
                api_key=current_user.ai_api_key
            ):
                # Formato SSE exigido pelo front-end para streaming
                yield f"data: {chunk}\n\n"
        except Exception as e:
            yield f"data: [ERRO NO SERVIÇO DE IA: {str(e)}]\n\n"

    return StreamingResponse(
        stream_generator(), 
        media_type="text/event-stream"
    )
