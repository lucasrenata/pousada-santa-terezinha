"""Endpoint para upload de arquivos."""

import os
import uuid
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status

from app.api.deps import get_current_admin_user

router = APIRouter()

# Diretório base de uploads (deve ser o mesmo configurado no main.py)
UPLOAD_DIR = "uploads"

@router.post("/image", status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    current_admin = Depends(get_current_admin_user)
):
    """
    Realiza o upload de uma imagem e retorna o caminho estático.
    """
    # 1. Validar se é uma imagem
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo enviado não é uma imagem válida."
        )

    # 2. Gerar nome único e extensão
    ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    # 3. Salvar o arquivo no diretório
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao salvar arquivo: {str(e)}"
        )
    finally:
        file.file.close()

    # 4. Retornar a URL pública
    return {"url": f"/static/{unique_filename}"}
