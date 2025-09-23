from fastapi import APIRouter
from pydantic import BaseModel
from agent_config import agent

router = APIRouter()
chat_history = []

class Pergunta(BaseModel):
    pergunta: str

@router.get("/")
def root():
    return {"message": "Agente NutriX com Gemini/ADK está funcionando!"}

@router.post("/responder")
async def responder(pergunta: Pergunta):
    global chat_history

    # Inclui histórico anterior
    full_prompt = "\n".join(chat_history + [f"Usuário: {pergunta.pergunta}"])

    # Chama o ADK
    response = await agent.run(full_prompt)
    resposta_texto = response.text

    # Atualiza histórico
    chat_history.append(f"Usuário: {pergunta.pergunta}")
    chat_history.append(f"Agente: {resposta_texto}")

    return {"resposta": resposta_texto}
