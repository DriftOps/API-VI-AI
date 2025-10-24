from fastapi import APIRouter, Header
from pydantic import BaseModel
from rag.rag_agent import responder_rag
import requests
import os
from datetime import datetime
import re
import json


SPRING_API_URL = os.getenv("SPRING_API_URL")

router = APIRouter()
chat_history = []


class Pergunta(BaseModel):
    pergunta: str


@router.get("/")
def root():
    return {"message": "Agente NutriX com Gemini/ADK + RAG está funcionando!"}

@router.get("/meals")
def get_meals(date: str = None, authorization: str = Header(None)):
    headers = {"Authorization": authorization}
    url = f"{SPRING_API_URL}/api/meals"
    if date:
        url += f"?date={date}"  # Assumindo que Spring suporta filter por data
    resp = requests.get(url, headers=headers)
    return resp.json()


@router.post("/responder")
async def responder(pergunta: Pergunta, authorization: str = Header(None)):
    global chat_history
    contexto_usuario = "Contexto do usuário não pôde ser carregado."

    try:
        # =======================
        # 🔑 Autenticação e Headers
        # =======================
        token = authorization.split(" ")[1] if authorization else None
        if not token:
            raise Exception("Token de autorização não fornecido.")
        headers = {"Authorization": f"Bearer {token}"}

        # =======================
        # 🧩 1. Buscar contexto principal (usuário + anamnese)
        # =======================
        user_url = f"{SPRING_API_URL}/api/users/context"
        response = requests.get(user_url, headers=headers)
        response.raise_for_status()
        full_context = response.json()

        user_data = full_context.get("user", {})
        anamnesis_data = full_context.get("anamnesis", {})

        # =======================
        # 🍽️ 2. Buscar refeições do usuário
        # =======================
        meals_url = f"{SPRING_API_URL}/api/meals"
        meals_response = requests.get(meals_url, headers=headers)

        if meals_response.status_code == 200:
            meals_data = meals_response.json()
            refeicoes_texto = "\n".join(
                [
                    f"- {m['type']}: {m['description']} "
                    f"({m['calories']} kcal, {m['protein']}g proteína, {m['carbs']}g carbs, {m['fat']}g gordura)"
                    for m in meals_data
                ]
            )
        else:
            refeicoes_texto = "Nenhuma refeição registrada recentemente."

        # =======================
        # 🧠 3. Montar contexto final para o modelo
        # =======================
        contexto_usuario = f"""
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
    # 💬 4. Montar prompt completo
    # =======================
    full_prompt = f"""
    {contexto_usuario}

    Histórico da conversa:
    {chr(10).join(chat_history)}

    Usuário: {pergunta.pergunta}

    Instrução: Responda ao usuário de forma amigável.
    Se a mensagem do usuário for um registro claro de uma refeição, extraia os dados nutricionais.
    Após sua resposta em texto, coloque os dados da refeição em um bloco <JSON> no seguinte formato:
    <JSON>
    {{
        "type": "...",
        "description": "...",
        "calories": ...,
        "protein": ...,
        "carbs": ...,
        "fat": ...
    }}
    </JSON>
    Se não for um registro de refeição, NÃO inclua o bloco <JSON>.
    """

    resposta_texto = responder_rag(full_prompt)

    # =======================
    # 💾 5. Processar e Salvar Refeição (se houver)
    # =======================
    meal_data = None
    texto_para_usuario = resposta_texto # Resposta padrão é o texto completo
    meal_saved = False

    # Procure pelo bloco <JSON> na resposta
    match = re.search(r"<JSON>\s*({.*?})\s*</JSON>", resposta_texto, re.DOTALL)
    
    if match and token:
        json_string = match.group(1)
        try:
            meal_data = json.loads(json_string)
            required_fields = ["type", "description", "calories", "protein", "carbs", "fat"]
            
            # Verifica se o JSON está completo
            if all(f in meal_data for f in required_fields):
                headers = {"Authorization": f"Bearer {token}"}
                post_url = f"{SPRING_API_URL}/api/meals"
                response = requests.post(post_url, headers=headers, json=meal_data)
                
                if response.status_code in [200, 201]:
                    meal_saved = True
                    # Remove o bloco JSON da resposta que vai para o chat
                    texto_para_usuario = re.sub(r"<JSON>.*?</JSON>", "", resposta_texto, flags=re.DOTALL).strip()
                else:
                    print(f"⚠️ Erro ao salvar refeição no Spring: {response.text}")
            
        except Exception as e:
            print(f"⚠️ Erro ao processar JSON da IA: {e}")
            pass # Ignora se o JSON for inválido

    # =======================
    # 🗣️ 6. Salvar no histórico e retornar
    # =======================
    chat_history.append(f"Usuário: {pergunta.pergunta}")
    chat_history.append(f"Agente: {texto_para_usuario}") # Salva a resposta limpa

    return {"resposta": texto_para_usuario, "meal_saved": meal_saved}

