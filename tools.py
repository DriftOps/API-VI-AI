from rag.rag_loader import load_documents_to_chroma
from rag.rag_retriever import retrieve_documents
import os

# --- Inicialização do RAG ---
# Carregamos a coleção aqui para que a ferramenta RAG possa usá-la
print("Carregando coleção RAG...")
doc_files = [os.path.join("data", f) for f in os.listdir("data") if f.endswith((".pdf", ".xlsx"))]
rag_collection = load_documents_to_chroma(doc_files)
print("Coleção RAG carregada com sucesso.")


# --- Ferramenta 1: Agente RAG ---
def perform_rag_search(query: str) -> dict:
    """
    Busca informações em documentos de nutrição (PDFs, Excel) para responder perguntas 
    técnicas, científicas ou sobre dados nutricionais específicos de alimentos.
    Use isso se o usuário perguntar sobre dietas, vitaminas, minerais, ou informações 
    que não estão no contexto básico do usuário.
    Não use para registrar refeições ou conversas gerais.
    """
    print(f"--- 🛠️ Ferramenta RAG ativada com a query: {query} ---")
    docs = retrieve_documents(rag_collection, query)
    contexto = "\n".join(docs)
    
    # Retorna o contexto encontrado para a IA
    return {"contexto_dos_documentos": contexto} 


# --- Ferramenta 2: Agente de Log de Refeição ---
def log_meal(
    type: str, 
    description: str, 
    calories: int, 
    protein: float, 
    carbs: float, 
    fat: float
) -> dict:
    """
    Prepara os dados de uma refeição para registro no banco de dados.
    Use esta ferramenta SEMPRE que o usuário declarar o que comeu 
    (ex: "comi um frango grelhado e arroz", "anote meu café da manhã: 2 ovos", "logar almoço").
    Extraia os valores nutricionais da melhor forma possível com base na descrição.
    """
    print(f"--- 🛠️ Ferramenta LOG_MEAL ativada (preparando dados) ---")
    
    # Esta função apenas valida e formata os dados.
    # O 'orchestrator' é quem fará a chamada de API (POST) para o Spring.
    return {
        "type": type,
        "description": description,
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat
    }