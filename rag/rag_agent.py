from agent_config import gemini_model
from rag.rag_loader import load_documents_to_chroma
from rag.rag_retriever import retrieve_documents
import os

doc_files = [
    os.path.join("data", f)
    for f in os.listdir("data")
    if f.endswith((".pdf", ".xlsx"))
]

collection = load_documents_to_chroma(doc_files)

def responder_rag(pergunta: str):
    docs = retrieve_documents(collection, pergunta)
    
    # Se não achar nada relevante no RAG
    if not docs:
        return "Não encontrei essa informação nos documentos. Reformule a pergunta."

    contexto = "\n".join(docs)

    prompt = f"""
Você é um assistente especializado. Responda SOMENTE com base no contexto fornecido.
Se a informação não estiver no contexto, diga que não sabe. NÃO invente nada.

Contexto confiável:
-------------------
{contexto}
-------------------

Pergunta:
{pergunta}

Regras:
- Não responda nada que não esteja no contexto
- Mantenha a resposta direta e objetiva
"""

    response = gemini_model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.1,      # Baixa temperatura = menos viagem
            "top_p": 0.9,
            "top_k": 40,
        }
    )
    
    return response.text