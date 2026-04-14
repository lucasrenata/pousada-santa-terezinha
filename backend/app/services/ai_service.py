import logging
from typing import AsyncGenerator
import openai
import google.generativeai as genai
from groq import AsyncGroq
from mistralai import Mistral

logger = logging.getLogger(__name__)

async def generate_ai_response_stream(
    message: str,
    course_title: str,
    lesson_context: str,
    ai_provider: str,
    ai_model: str,
    api_key: str
) -> AsyncGenerator[str, None]:
    """
    Gera um STREAM de resposta do Co-Professor usando o provedor e modelo escolhido.
    Yields: Chunks de texto (tokens) conforme são gerados.
    """
    
    system_prompt = f"""Você é o Co-Professor da plataforma ParcerIA. 
Sua missão é ajudar o aluno a entender o conteúdo do curso "{course_title}".
Contexto da aula atual: {lesson_context}

Instruções:
1. Seja didático, encorajador e profissional.
2. Se a dúvida não for relacionada ao curso, tente gentilmente trazer o foco de volta.
3. Use Markdown para formatar suas respostas.
4. Responda em Português (Brasil).
"""

    try:
        # ------------------------------------------------------------------
        # OPENAI (Streaming)
        # ------------------------------------------------------------------
        if ai_provider == 'openai':
            client = openai.AsyncOpenAI(api_key=api_key)
            stream = await client.chat.completions.create(
                model=ai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                stream=True
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        # ------------------------------------------------------------------
        # GEMINI (Streaming)
        # ------------------------------------------------------------------
        elif ai_provider == 'gemini':
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name=ai_model,
                system_instruction=system_prompt
            )
            # O Gemini tem um metodo stream=True específico
            response = await model.generate_content_async(message, stream=True)
            async for chunk in response:
                if chunk.text:
                    yield chunk.text

        # ------------------------------------------------------------------
        # GROQ (Streaming)
        # ------------------------------------------------------------------
        elif ai_provider == 'groq':
            client = AsyncGroq(api_key=api_key)
            stream = await client.chat.completions.create(
                model=ai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                stream=True
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        # ------------------------------------------------------------------
        # MISTRAL (Streaming)
        # ------------------------------------------------------------------
        elif ai_provider == 'mistral':
            client = Mistral(api_key=api_key)
            stream_response = await client.chat.stream_async(
                model=ai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
            )
            async for chunk in stream_response:
                if chunk.data.choices[0].delta.content:
                    yield chunk.data.choices[0].delta.content

        else:
            yield f"[Erro: Provedor {ai_provider} não suportado para streaming]"

    except Exception as e:
        logger.error(f"Erro ao gerar stream da IA ({ai_provider}): {str(e)}")
        yield f"\n\n[Ocorreu um erro na conexão com a IA: {str(e)}]"

async def generate_ai_response(
    message: str,
    course_title: str,
    lesson_context: str,
    ai_provider: str,
    ai_model: str,
    api_key: str
) -> str:
    """Wrapper síncrono para compatibilidade que consome o stream e retorna o texto completo."""
    full_text = ""
    async for chunk in generate_ai_response_stream(
        message, course_title, lesson_context, ai_provider, ai_model, api_key
    ):
        if not chunk.startswith("\n\n[Ocorreu um erro"):
            full_text += chunk
    return full_text
