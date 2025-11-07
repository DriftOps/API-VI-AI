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

    # =======================================================
# (NOVA) Ferramenta para Criar Dieta
# =======================================================

class CreateDietArgs(BaseModel):
    """Argumentos para a ferramenta create_diet."""
    title: str = Field(..., description="O título para a nova dieta. Ex: 'Plano de 8 semanas'.")
    endDate: str = Field(..., description="A data final da dieta, no formato YYYY-MM-DD. Deve ser uma data futura.")
    targetWeight: float = Field(..., description="O peso alvo que o usuário quer atingir em kg.")
    user_id: int = Field(..., description="ID do usuário (passado automaticamente pelo orquestrador).")
    user_context: str = Field(..., description="Contexto completo do usuário (passado automaticamente pelo orquestrador).")
    token: str = Field(..., description="Token de autorização (passado automaticamente pelo orquestrador).")

@tool("create_diet", args_schema=CreateDietArgs, return_direct=False)
async def create_diet(title: str, endDate: str, targetWeight: float, user_id: int, user_context: str, token: str) -> str:
    """
    Cria uma nova dieta para o usuário. 
    Esta ferramenta primeiro calcula as metas calóricas necessárias usando IA 
    e depois registra a dieta no backend.
    """
    try:
        # --- ETAPA 1: Chamar a IA para calcular calorias ---
        # Esta é uma sub-chamada da IA, focada apenas em cálculo
        prompt = f"""
        Analise o seguinte contexto de usuário:
        {user_context}
        
        A meta é criar uma dieta para atingir {targetWeight} kg até {endDate}.
        
        Com base em todos os dados (idade, peso, altura, gênero, nível de atividade, objetivo), 
        calcule DUAS coisas:
        1.  'base_daily_calories': A meta de calorias diárias (ex: TMB * fator de atividade - déficit calórico).
        2.  'safe_metabolic_floor': O piso metabólico seguro (TMB ou um valor mínimo como 1200 kcal para mulheres ou 1500 kcal para homens) 
            abaixo do qual a IA nunca deve reajustar.
        
        Responda APENAS com um objeto JSON válido, sem explicações, markdown ou "```json".
        Exemplo:
        {{
          "base_daily_calories": 1850,
          "safe_metabolic_floor": 1400
        }}
        """
        
        print("--- Gerando cálculo de calorias ---")
        response = await model.generate_content_async(prompt)
        
        cleaned_response = response.text.strip()
        calorie_data = json.loads(cleaned_response)
        
        base_calories = calorie_data.get("base_daily_calories")
        safe_floor = calorie_data.get("safe_metabolic_floor")
        
        if not base_calories or not safe_floor:
            raise Exception(f"IA falhou em calcular as calorias. Resposta: {cleaned_response}")

        print(f"--- Calorias calculadas: Base={base_calories}, Piso={safe_floor} ---")

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