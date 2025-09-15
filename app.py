from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline

# Inicializa FastAPI
app = FastAPI()

# Estrutura da requisição
class ChatRequest(BaseModel):
    message: str

# Carregar modelo local do Hugging Face
chatbot = pipeline("text-generation", model="microsoft/DialoGPT-medium")

@app.post("/chat")
def chat(request: ChatRequest):
    try:
        user_message = request.message
        response = chatbot(user_message, max_length=100, num_return_sequences=1)
        reply = response[0]["generated_text"]
        return {"reply": reply}
    except Exception as e:
        return {"reply": f"Erro ao gerar resposta: {e}"}
