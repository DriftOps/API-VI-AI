from fastapi import APIRouter, Header
from pydantic import BaseModel, Field
from orchestrator import run_orchestrator # Importa o orquestrador
import requests
import os
from typing import List

SPRING_API_URL = os.getenv("SPRING_API_URL")
router = APIRouter()


class Pergunta(BaseModel):
    pergunta: str

# =======================================================
# DTOs (Pydantic Models) para o Rebalanceador de Dieta
# =======================================================
class DailyData(BaseModel):
    target_calories: int
    consumed_calories: int

class AiBalanceRequest(BaseModel):
    base_calories: int
    safe_metabolic_floor: int
    recent_days: List[DailyData]

# =======================================================
# (NOVO) Endpoint de Rebalanceamento da Dieta
# =======================================================
@router.post("/ai/balance-diet")
def balance_diet(request: AiBalanceRequest):
    """
    Este endpoint é chamado pelo backend Java (DietBalanceJob) diariamente.
    Ele recebe o histórico de consumo e recalcula a meta para os próximos dias.
    """
    base_calories = request.base_calories
    safe_floor = request.safe_metabolic_floor
    recent_days = request.recent_days

    if not recent_days:
        return {
            "new_adjusted_calories": base_calories,
            "ai_rationale": "Iniciando a dieta. Mantenha-se focado na sua meta base!"
        }

    # --- LÓGICA PRINCIPAL (O "DETALHE IMPORTANTE") ---
    
    # Usar apenas dias que já passaram (onde consumo > 0 ou target existe)
    valid_days = [d for d in recent_days if d.consumed_calories > 0 or d.target_calories > 0]
    if not valid_days:
        valid_days = recent_days[:1] # Pega o primeiro dia se nenhum tiver consumo

    avg_target = sum(d.target_calories for d in valid_days) / len(valid_days)
    avg_consumed = sum(d.consumed_calories for d in valid_days) / len(valid_days)
    
    # Limite de tolerância (ex: 5%)
    tolerance_threshold = avg_target * 1.05
    
    new_target = base_calories
    rationale = f"Você está indo bem, mantendo o consumo próximo da meta de {base_calories} kcal. Continue assim!"

    if avg_consumed > tolerance_threshold:
        # Usuário está comendo DEMAIS
        avg_excess = avg_consumed - avg_target
        
        # Fator de correção suave (ex: 50%)
        correction_factor = 0.5 
        correction_value = avg_excess * correction_factor
        
        new_target = base_calories - correction_value
        
        # --- A REGRA DE OURO (PISO MÍNIMO) ---
        if new_target < safe_floor:
            new_target = safe_floor
            rationale = (f"Notei que seu consumo médio ({int(avg_consumed)} kcal) está acima da meta. "
                         f"Ajustei sua meta para {int(new_target)} kcal, que é o seu piso metabólico seguro. "
                         f"Vamos focar em voltar ao plano, mas sem medidas extremas!")
        else:
            rationale = (f"Notei que seu consumo médio ({int(avg_consumed)} kcal) ficou um pouco acima da meta. "
                         f"Isso é normal! Para manter o progresso, ajustei sua meta suavemente "
                         f"para {int(new_target)} kcal nos próximos dias.")

    elif avg_consumed < (avg_target * 0.85) and avg_consumed > 0:
        # Usuário está comendo DE MENOS (também é um problema)
        new_target = base_calories
        rationale = (f"Notei que seu consumo médio ({int(avg_consumed)} kcal) está bem abaixo da sua meta. "
                     f"Lembre-se que um déficit muito grande pode prejudicar seu metabolismo. "
                     f"Sua meta continua sendo {int(new_target)} kcal. Tente se aproximar dela.")

    return {
        "new_adjusted_calories": int(new_target),
        "ai_rationale": rationale
    }

# =======================================================
# Endpoints Existentes (Sem alteração de assinatura)
# =======================================================

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
    contexto_usuario_completo = "Contexto do usuário não pôde ser carregado."
    token = None
    user_id = None # (NOVO)
    
    historico_para_gemini = []
    feedback_para_contexto = []

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
        user_id = user_data.get("id") # (NOVO) Captura o ID do usuário

        # =======================
        # 🍽️ 3. Buscar refeições
        # =======================
        # (Seu código original - sem alteração)
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
        # 💬 3b. Buscar Histórico de Chat e Feedback
        # =======================
        # (Seu código original - sem alteração)
        history_url = f"{SPRING_API_URL}/api/chat/history"
        history_response = requests.get(history_url, headers=headers)
        
        if history_response.status_code == 200:
            chat_history_data = history_response.json()
            for msg in chat_history_data:
                # ... (lógica de processamento de histórico) ...
                sender = msg.get('sender')
                message = msg.get('message')
                feedback = msg.get('userFeedback') 

                if sender == 'user':
                    historico_para_gemini.append(f"Usuário: {message}")
                elif sender == 'assistant':
                    historico_para_gemini.append(f"Agente: {message}")
                    
                    if feedback:
                        pergunta_anterior = "N/A"
                        if historico_para_gemini and len(historico_para_gemini) > 1:
                            pergunta_anterior = historico_para_gemini[-2]
                        
                        feedback_para_contexto.append(
                            f"- Pergunta: \"{pergunta_anterior[9:70]}...\"\n"
                            f"- Resposta: \"{message[:70]}...\"\n"
                            f"- Feedback do Usuário: {feedback.upper()}"
                        )
        else:
            print(f"⚠️ Erro ao buscar histórico: {history_response.text}")


        # =======================
        # 🥗 3c. [NOVO] Buscar Dieta Ativa
        # =======================
        dieta_ativa_texto = "Nenhuma dieta ativa no momento."
        dieta_ativa_obj = None # (NOVO)
        if user_id:
            try:
                # O endpoint que criamos no Java
                diet_url = f"{SPRING_API_URL}/api/diets/active/{user_id}"
                diet_response = requests.get(diet_url, headers=headers)
                
                if diet_response.status_code == 200:
                    dieta_ativa_obj = diet_response.json() # (NOVO) Salva o objeto da dieta
                    dieta_ativa_texto = f"""
                    - Título: {dieta_ativa_obj.get('title')}
                    - Período: {dieta_ativa_obj.get('startDate')} a {dieta_ativa_obj.get('endDate')}
                    - Meta de Peso: {dieta_ativa_obj.get('targetWeight')} kg
                    - Meta Base de Calorias: {dieta_ativa_obj.get('baseDailyCalories')} kcal
                    - Último Racional da IA: {dieta_ativa_obj.get('aiRationale', 'Nenhum')}
                    """
                elif diet_response.status_code == 404:
                    dieta_ativa_texto = "Nenhuma dieta ativa encontrada. Você pode pedir para eu criar uma."
                else:
                    # Informa o erro sem quebrar
                    dieta_ativa_texto = f"Não foi possível buscar a dieta (status {diet_response.status_code})."
            except Exception as diet_err:
                print(f"⚠️ Erro ao buscar dieta: {diet_err}")
                dieta_ativa_texto = "Erro ao conectar ao serviço de dietas."


        # =======================
        # 🧠 4. Montar contexto final para o modelo
        # =======================
        feedback_contexto_str = "Nenhum feedback registrado ainda."
        if feedback_para_contexto:
            feedback_contexto_str = "\n\n".join(feedback_para_contexto)

        contexto_usuario_completo = f"""
        Dados do usuário:
        - ID: {user_data.get('id', 'N/A')} (Use isso para ferramentas)
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

        ---
        [NOVO] DIETA ATIVA:
        {dieta_ativa_texto}
        ---

        [NOVO] FEEDBACK DO USUÁRIO SOBRE RESPOSTAS ANTERIORES:
        Use este feedback para aprender e ajustar suas respostas futuras.
        Respostas com 'NEGATIVE' devem ser evitadas. Respostas com 'POSITIVE' são bons exemplos.
        
        {feedback_contexto_str}
        ---
        """

    except requests.exceptions.HTTPError as http_err:
        print(f"⚠️ Erro HTTP ao buscar contexto: {http_err}")
        print(f"⚠️ Resposta do servidor: {http_err.response.text}")
    except Exception as e:
        print(f"⚠️ Erro ao buscar contexto: {e}")

    # =======================
    # 🤖 5. Chamar o Orquestrador
    # =======================
    
    result = await run_orchestrator(
        pergunta=pergunta.pergunta,
        full_context=contexto_usuario_completo,
        chat_history=historico_para_gemini,
        authorization_token=token,
        user_id=user_id, # (NOVO) Passa o user_id para as ferramentas
        active_diet=dieta_ativa_obj # (NOVO) Passa a dieta para as ferramentas
    )

    # Retorna a resposta final, agora incluindo 'diet_created'
    return {
        "resposta": result['resposta'], 
        "meal_saved": result['meal_saved'],
        "diet_created": result.get('diet_created', False) # (NOVO)
    }