from agent_config import gemini_model 
from rag.rag_loader import load_documents_to_chroma
from rag.rag_retriever import retrieve_documents 
import os

# Lista de arquivos PDF + XLSX
doc_files = [os.path.join("data", f) for f in os.listdir("data") if f.endswith((".pdf", ".xlsx"))]

# Carrega os documentos no Chroma
collection = load_documents_to_chroma(doc_files)

def responder_rag(pergunta: str):
    docs = retrieve_documents(collection, pergunta)
    contexto = "\n".join(docs)

    prompt = f"""
Use as informações do contexto abaixo para responder à pergunta do usuário.

Contexto adicional dos documentos:
---
{contexto}
---

Pergunta do usuário:
{pergunta}
"""
    response = gemini_model.generate_content(prompt)
    return response.text
