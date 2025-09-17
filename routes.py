from fastapi import APIRouter
from pydantic import BaseModel
from agent_config import gemini_model

router = APIRouter()

# Memória simples
chat_history = []

class Pergunta(BaseModel):
    pergunta: str

@router.get("/")
def root():
    return {"message": "✅ Agente de nutrição com Gemini está funcionando!"}

@router.post("/responder")
def responder(pergunta: Pergunta):
    global chat_history

    prompt = (
        "Você é um assistente especializado em nutrição. "
        "Responda de forma clara e educativa.\n\n"
        "Base inicial:\n"
        "- Frutas e vegetais são ricos em vitaminas e fibras.\n"
        "- Proteínas ajudam na construção muscular e saciedade.\n"
        "- Água é essencial para hidratação.\n"
        "- Evitar excesso de açúcar e alimentos ultraprocessados é saudável.\n"
        "- Uma alimentação equilibrada inclui carboidratos, proteínas, gorduras saudáveis, vitaminas e minerais.\n\n"
        "Histórico da conversa:\n"
        f"{chat_history}\n"
        f"Usuário: {pergunta.pergunta}\nAgente:"
    )

    response = gemini_model.generate_content(prompt)
    resposta_texto = response.text

    # Atualizar histórico
    chat_history.append(f"Usuário: {pergunta.pergunta}")
    chat_history.append(f"Agente: {resposta_texto}")

    return {"resposta": resposta_texto}
