from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProgressCreate(BaseModel):
    lesson_id: UUID


class ProgressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    lesson_id: UUID
    completed_at: datetime
