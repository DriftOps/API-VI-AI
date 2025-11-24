# routes.py
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
    image: str | None = None

# =======================================================
# (NOVO) DTOs (Pydantic Models) para o Rebalanceador de Dieta
# =======================================================
class DailyData(BaseModel):
    target_calories: int
    consumed_calories: int

class AiBalanceRequest(BaseModel):
    base_calories: int
    safe_metabolic_floor: int
    recent_days: List[DailyData]

class AiBalanceResponse(BaseModel):
    next_days_targets: List[int] # AGORA É UMA LISTA
    ai_rationale: str

# =======================================================
# (NOVO) Endpoint de Rebalanceamento da Dieta
# =======================================================
@router.post("/ai/balance-diet")
def balance_diet(request: AiBalanceRequest):
    base_calories = request.base_calories
    safe_floor = request.safe_metabolic_floor
    recent_days = request.recent_days

    # 1. Definição padrão (Plano Base) - 7 dias com a meta base
    standard_plan = [base_calories] * 7 

    if not recent_days:
        return {
            "next_days_targets": standard_plan,
            "ai_rationale": "Iniciando a dieta. Mantenha-se focado na sua meta base!"
        }

    # 2. Calcular Média e Excesso
    valid_days = [d for d in recent_days if d.consumed_calories > 0]
    if not valid_days:
        return { "next_days_targets": standard_plan, "ai_rationale": "Sem dados suficientes ainda." }

    avg_target = sum(d.target_calories for d in valid_days) / len(valid_days)
    avg_consumed = sum(d.consumed_calories for d in valid_days) / len(valid_days)
    
    rationale = f"Seu consumo está dentro do planejado. Mantive as metas base."
    final_plan = list(standard_plan)

    # 3. Lógica de Recuperação Inteligente
    if avg_consumed > (avg_target * 1.05): # Se excedeu 5%
        daily_excess = avg_consumed - avg_target
        # Supondo que queremos recuperar esse excesso diluído em 3 dias (33% por dia)
        # para não ser muito agressivo
        debt_per_day = daily_excess * 0.5 # Cobra 50% do excesso (fator de suavização)
        
        # Cria a curva de recuperação
        rationale = "Notei o excesso calórico recente. Ajustei as metas dos próximos 3 dias para compensar suavemente, sem restringir demais."
        
        for i in range(7):
            if i < 3: # Nos primeiros 3 dias, aplica a redução
                new_val = base_calories - debt_per_day
                # Regra do Piso Seguro (Nunca baixar demais)
                if new_val < safe_floor:
                    new_val = safe_floor
                final_plan[i] = int(new_val)
            else:
                # Do 4º dia em diante, volta ao normal
                final_plan[i] = base_calories

    elif avg_consumed < (avg_target * 0.85): # Se comeu muito pouco
        rationale = "Você está comendo abaixo da meta. Cuidado para não perder massa magra. Mantive a meta base para você recuperar."
        final_plan = standard_plan # Mantém a base para incentivar comer

    return {
        "next_days_targets": final_plan,
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
    user_id = None
    dieta_ativa_obj = None
    
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
        image_data=pergunta.image,
        user_coords={"lat": pergunta.latitude, "lng": pergunta.longitude},
        full_context=contexto_usuario_completo,
        chat_history=historico_para_gemini,
        authorization_token=token,
        user_id=user_id,
        active_diet=dieta_ativa_obj
    )

    # Retorna a resposta final, agora incluindo 'diet_created'
    return {
        "resposta": result['resposta'], 
        "meal_saved": result['meal_saved'],
        "diet_created": result.get('diet_created', False) # (NOVO)
    }