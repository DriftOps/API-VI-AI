from agent_config import gemini_model 
from rag.rag_loader import load_csv_to_chroma
from rag.rag_retriever import retrieve_documents 

# Carregar CSVs e criar collection
csv_files = ["data/taco-db-nutrientes.csv", "data/taco-db-nutrientes-2.csv"]
# Garanta que os arquivos CSV estejam no caminho correto
collection = load_csv_to_chroma(csv_files) 

def responder_rag(pergunta: str):
    # Busca os documentos relevantes no ChromaDB
    docs = retrieve_documents(collection, pergunta)
    contexto = "\n".join(docs)

    # Cria prompt enriquecido
    prompt = f"""
Use as informações do contexto abaixo para responder à pergunta do usuário.

Contexto adicional dos documentos:
---
{contexto}
---

Pergunta do usuário:
{pergunta}
"""

    # GERA A RESPOSTA DIRETAMENTE COM O MODELO
    response = gemini_model.generate_content(prompt)
    return response.text