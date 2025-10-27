from fastapi import APIRouter, Header
from pydantic import BaseModel
from orchestrator import run_orchestrator # Importa o novo orquestrador
import requests
import os

SPRING_API_URL = os.getenv("SPRING_API_URL")
router = APIRouter()

# !! AVISO: O chat_history global não é ideal para produção (não escala para múltiplos usuários)
# Mas estou mantendo para não quebrar sua lógica atual.
chat_history = []


class Pergunta(BaseModel):
    pergunta: str


@router.get("/")
def root():
    return {"message": "Agente NutriX com Gemini (Orquestrador) + RAG está funcionando!"}

@router.get("/meals")
def get_meals(date: str = None, authorization: str = Header(None)):
    # (Seu código original - sem alteração)
    headers = {"Authorization": authorization}
    url = f"{SPRING_API_URL}/api/meals"
    if date:
        url += f"?date={date}"
    resp = requests.get(url, headers=headers)
    return resp.json()


@router.post("/responder")
async def responder(pergunta: Pergunta, authorization: str = Header(None)):
    global chat_history
    contexto_usuario_completo = "Contexto do usuário não pôde ser carregado."
    token = None

    try:
        # =======================
        # 🔑 1. Autenticação e Headers
        # =======================
        token = authorization.split(" ")[1] if authorization else None
        if not token:
            raise Exception("Token de autorização não fornecido.")
        headers = {"Authorization": f"Bearer {token}"}

        # =======================
        # 🧩 2. Buscar contexto (Usuário + Anamnese)
        # =======================
        user_url = f"{SPRING_API_URL}/api/users/context"
        response = requests.get(user_url, headers=headers)
        response.raise_for_status()
        full_context = response.json()

        user_data = full_context.get("user", {})
        anamnesis_data = full_context.get("anamnesis", {})

        # =======================
        # 🍽️ 3. Buscar refeições
        # =======================
        meals_url = f"{SPRING_API_URL}/api/meals"
        meals_response = requests.get(meals_url, headers=headers)
        refeicoes_texto = "Nenhuma refeição registrada recentemente."

        if meals_response.status_code == 200:
            meals_data = meals_response.json()
            refeicoes_texto = "\n".join(
                [
                    f"- {m['type']}: {m['description']} "
                    f"({m['calories']} kcal, {m['protein']}g proteína, {m['carbs']}g carbs, {m['fat']}g gordura)"
                    for m in meals_data
                ]
            )

        # =======================
        # 🧠 4. Montar contexto final para o modelo
        # =======================
        # (Seu código original de montagem de contexto - sem alteração)
        contexto_usuario_completo = f"""
        Dados do usuário:
        - Nome: {user_data.get('name', 'N/A')}
        - Gênero: {user_data.get('gender', 'N/A')}
        - Idade: {user_data.get('age', 'N/A')} anos
        - Peso: {user_data.get('weight', 'N/A')} kg
        - Altura: {user_data.get('height', 'N/A')} cm

        Anamnese e Hábitos:
        - Objetivo Principal: {anamnesis_data.get('mainGoal', 'N/A')}
        - Condições Médicas: {anamnesis_data.get('medicalConditions', 'Nenhuma')}
        - Alergias: {anamnesis_data.get('allergies', 'Nenhuma')}
        - Cirurgias: {anamnesis_data.get('surgeries', 'Nenhuma')}
        - Atividade Física: {anamnesis_data.get('activityType', 'N/A')} ({anamnesis_data.get('frequency', 'N/A')})
        - Minutos de Atividade por Dia: {anamnesis_data.get('activityMinutesPerDay', 'N/A')}
        - Qualidade do Sono: {anamnesis_data.get('sleepQuality', 'N/A')}
        - Acorda durante a noite: {anamnesis_data.get('wakesDuringNight', 'N/A')}
        - Frequência Intestinal: {anamnesis_data.get('bowelFrequency', 'N/A')}
        - Nível de Estresse: {anamnesis_data.get('stressLevel', 'N/A')}
        - Consumo de Álcool: {anamnesis_data.get('alcoholUse', 'N/A')}
        - Fumante: {'Sim' if anamnesis_data.get('smoking') else 'Não'}
        - Nível de Hidratação: {anamnesis_data.get('hydrationLevel', 'N/A')}
        - Medicação Contínua: {'Sim' if anamnesis_data.get('continuousMedication') else 'Não'}

        Refeições Recentes:
        {refeicoes_texto}
        """

    except requests.exceptions.HTTPError as http_err:
        print(f"⚠️ Erro HTTP ao buscar contexto: {http_err}")
        print(f"⚠️ Resposta do servidor: {http_err.response.text}")
    except Exception as e:
        print(f"⚠️ Erro ao buscar contexto: {e}")

    # =======================
    # 🤖 5. Chamar o Orquestrador
    # =======================
    # Removemos toda a lógica de prompt, RAG e parsing de JSON daqui.
    
    result = await run_orchestrator(
        pergunta=pergunta.pergunta,
        full_context=contexto_usuario_completo,
        chat_history=chat_history,
        authorization_token=token 
    )

    # =======================
    # 🗣️ 6. Salvar no histórico e retornar
    # =======================
    chat_history.append(f"Usuário: {pergunta.pergunta}")
    chat_history.append(f"Agente: {result['resposta']}") 

    # Retorna a resposta final do orquestrador
    return {"resposta": result['resposta'], "meal_saved": result['meal_saved']}