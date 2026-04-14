from pydantic import BaseModel

class VisitTrack(BaseModel):
    visitorId: str

class VisitResponse(BaseModel):
    user_status: str
    system_prompt: str
