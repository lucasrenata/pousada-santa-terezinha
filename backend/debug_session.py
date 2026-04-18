import json
from database import SessionLocal
import models
import sys

def debug_session(session_id):
    db = SessionLocal()
    try:
        session = db.query(models.SessionState).filter(models.SessionState.session_id == session_id).first()
        if not session:
            print(f"Sessão {session_id} não encontrada no banco.")
            return
        
        print(f"=== DEBUG SESSÃO: {session_id} ===")
        print(f"Estado Atual: {session.current_state}")
        print(f"Contexto (JSON):")
        context = json.loads(session.context_json) if session.context_json else {}
        print(json.dumps(context, indent=2, ensure_ascii=False))
        print("===============================")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python debug_session.py <session_id>")
    else:
        debug_session(sys.argv[1])
