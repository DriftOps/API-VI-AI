from rag.rag_loader import load_documents_to_chroma
from rag.rag_retriever import retrieve_documents
import os
import requests
import json
import google.generativeai as genai
from pydantic import BaseModel, Field
from langchain_core.tools import tool

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

def create_diet(
    title: str, 
    endDate: str, 
    targetWeight: float
) -> dict:
    """
    Prepara os parâmetros para criar uma nova dieta para o usuário.
    Use esta ferramenta quando o usuário pedir para 'criar uma dieta', 
    'iniciar um plano alimentar', 'fazer uma nova dieta'.
    Extraia o 'title' (título), 'endDate' (data final YYYY-MM-DD), 
    e 'targetWeight' (peso alvo em kg).
    """
    print(f"--- 🛠️ Ferramenta CREATE_DIET ativada (preparando dados) ---")
    
    # Apenas retorna os args. O Orquestrador faz a sub-chamada da IA e a chamada de API.
    return {
        "title": title,
        "endDate": endDate,
        "targetWeight": targetWeight
    }

def create_recipe(query: str, constraints: str = None) -> dict:
    """
    Prepara os parâmetros para a IA gerar uma nova receita personalizada.
    Use esta ferramenta SEMPRE que o usuário pedir para 'criar uma receita', 
    'me dê uma ideia de jantar', 'sugira um prato com X', 'o que posso fazer para o almoço'.
    O orquestrador usará isso para gerar a receita com base no contexto do usuário.
    """
    print(f"--- 🛠️ Ferramenta CREATE_RECIPE ativada (preparando dados) ---")
    
    # Apenas retorna os args. O Orquestrador faz a sub-chamada da IA.
    return {
        "query": query,
        "constraints": constraints or "Nenhuma restrição adicional."
    }

def update_anamnesis(field: str, value: str) -> dict:
    """
    Atualiza um campo específico da anamnese do usuário no banco de dados.
    Use esta ferramenta Imediatamente após o usuário responder a uma pergunta de anamnese.
    
    Args:
        field (str): O nome do campo técnico (ex: 'mainGoal', 'sleepQuality').
        value (str): O valor correspondente ao ENUM ou o texto livre (ex: 'WEIGHT_LOSS', 'GOOD', 'true').
    """
    print(f"--- Ferramenta UPDATE_ANAMNESIS ativada: {field} = {value} ---")
    return {
        "field": field,
        "value": value
    }