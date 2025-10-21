from fastapi import APIRouter
from pydantic import BaseModel
from rag.rag_agent import responder_rag
from fastapi import Header
import requests
import os

SPRING_API_URL = os.getenv("SPRING_API_URL")

router = APIRouter()
chat_history = []

class Pergunta(BaseModel):
    pergunta: str

@router.get("/")
def root():
    return {"message": "Agente NutriX com Gemini/ADK + RAG está funcionando!"}

@router.post("/responder")
async def responder(pergunta: Pergunta, authorization: str = Header(None)):
    global chat_history
    contexto_usuario = "Contexto do usuário não pôde ser carregado."

    try:
        token = authorization.split(" ")[1] if authorization else None
        if not token:
            raise Exception("Token de autorização não fornecido.")

        headers = {"Authorization": f"Bearer {token}"}
        url = os.getenv('SPRING_API_URL')
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        full_context = response.json()

        # --- LINHAS ADICIONADAS ---
        # Extrai os dados de 'user' e 'anamnesis' do objeto principal
        user_data = full_context.get('user', {})
        anamnesis_data = full_context.get('anamnesis', {})
        # ---------------------------

        # Agora as variáveis user_data e anamnesis_data existem e o código abaixo funciona
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
        """

    except requests.exceptions.HTTPError as http_err:
        print(f"⚠️ Erro HTTP ao buscar contexto: {http_err}")
        print(f"⚠️ Resposta do servidor: {http_err.response.text}")
    except Exception as e:
        print(f"⚠️ Erro ao buscar contexto: {e}")

    # O restante do código continua normalmente
    full_prompt = f"""
    {contexto_usuario}

    Histórico da conversa:
    {chr(10).join(chat_history)}

    Usuário: {pergunta.pergunta}
    """

    resposta_texto = responder_rag(full_prompt)

    chat_history.append(f"Usuário: {pergunta.pergunta}")
    chat_history.append(f"Agente: {resposta_texto}")

    return {"resposta": resposta_texto}