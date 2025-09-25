# rag_agent.py
from agent_config import root_agent
from rag_loader import load_csv_to_chroma
from rag_retriever import create_retriever

# Carregar CSVs
csv_files = ["data/taco-db-nutrientes.csv", "data/taco-db-nutrientes-2.csv"]
collection = load_csv_to_chroma(csv_files)
retriever = create_retriever(collection)

def responder_rag(pergunta: str):
    # Recupera documentos mais relevantes
    docs = retriever.get_relevant_documents(pergunta)
    contexto = "\n".join([doc.page_content for doc in docs])

    # Cria prompt enriquecido
    prompt = f"""
Você é um assistente especializado em nutrição. Use as informações abaixo para responder de forma clara e prática:

Contexto adicional dos documentos:
{contexto}

Pergunta do usuário:
{pergunta}
"""

    # Rodar no ADK
    response = root_agent.run(prompt)
    return response.text
