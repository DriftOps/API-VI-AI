from rag.rag_loader import load_documents_to_chroma
from rag.rag_retriever import retrieve_documents
import os
import requests  # <-- 1ª CORREÇÃO: Importar requests
import json
import google.generativeai as genai


# --- Inicialização do RAG ---
# (Seu código original - sem alteração)
print("Carregando coleção RAG...")
doc_files = [os.path.join("data", f) for f in os.listdir("data") if f.endswith((".pdf", ".xlsx"))]
rag_collection = load_documents_to_chroma(doc_files)
print("Coleção RAG carregada com sucesso.")


# --- Ferramenta 1: Agente RAG ---
# (Seu código original - sem alteração)
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
# (Seu código original - sem alteração)
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
    
    # (Esta lógica está correta, pois o 'orchestrator' faz a chamada de API)
    return {
        "type": type,
        "description": description,
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat
    }

# =======================================================
# (CORRIGIDO) Ferramenta para Criar Dieta (Simplificada)
# =======================================================

# (REMOVIDO) Classe CreateDietArgs
# (REMOVIDO) Decorator @tool

# <-- 2ª CORREÇÃO: Assinatura da função limpa
async def create_diet(
    title: str, 
    endDate: str, 
    targetWeight: float, 
    user_id: int, 
    token: str,
    base_calories: int, # <-- Argumento vem do orquestrador
    safe_floor: int     # <-- Argumento vem do orquestrador
) -> str:
    """
    Cria uma nova dieta para o usuário. 
    Esta ferramenta é chamada DEPOIS que o orquestrador já calculou as metas 
    calóricas e ela apenas salva os dados no backend.
    """
    try:
        # (REMOVIDO) ETAPA 1 (Cálculo de calorias) foi movida para o orquestrador.

        # --- ETAPA 2: Criar o payload para o Spring Boot ---
        payload = {
            "userId": user_id,
            "title": title,
            "endDate": endDate,
            "targetWeight": targetWeight,
            "baseDailyCalories": base_calories,
            "safeMetabolicFloor": safe_floor
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # <-- 3ª CORREÇÃO: Definir a URL do Spring
        SPRING_API_URL = os.getenv("SPRING_API_URL")
        if not SPRING_API_URL:
            raise Exception("SPRING_API_URL não está configurada no ambiente.")
            
        url = f"{SPRING_API_URL}/api/diets"
        
        # --- ETAPA 3: Chamar o backend Java ---
        print(f"--- Enviando para o Spring: {url} ---")
        spring_response = requests.post(url, headers=headers, json=payload)
        spring_response.raise_for_status() # Lança erro se não for 2xx
        
        # --- ETAPA 4: Retornar sucesso ---
        return (f"Dieta '{title}' criada com sucesso! "
                f"Calculei uma meta base de {base_calories} kcal/dia. "
                f"Vou reajustar isso dinamicamente. O usuário já pode ver o plano na tela 'Minha Dieta'.")
                
    except requests.exceptions.HTTPError as http_err:
        print(f"Erro HTTP ao criar dieta: {http_err.response.text}")
        return f"Erro ao salvar a dieta no backend: {http_err.response.text}"
    except Exception as e:
        print(f"Erro geral ao criar dieta: {e}")
        return f"Erro ao criar dieta: {e}"