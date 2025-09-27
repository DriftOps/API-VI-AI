from fastapi import APIRouter
from pydantic import BaseModel
from rag.rag_agent import responder_rag

router = APIRouter()
chat_history = []

class Pergunta(BaseModel):
    pergunta: str

@router.get("/")
def root():
    return {"message": "Agente NutriX com Gemini/ADK + RAG está funcionando!"}

@router.post("/responder")
async def responder(pergunta: Pergunta):
    global chat_history

    # Inclui histórico anterior no prompt, se quiser contexto
    full_prompt = "\n".join(chat_history + [f"Usuário: {pergunta.pergunta}"])

    # Chama a função RAG
    resposta_texto = responder_rag(full_prompt)

    # Atualiza histórico
    chat_history.append(f"Usuário: {pergunta.pergunta}")
    chat_history.append(f"Agente: {resposta_texto}")

    return {"resposta": resposta_texto}
