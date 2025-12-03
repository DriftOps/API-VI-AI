import os
import json
import base64
import io
from PIL import Image
import google.generativeai as genai
from typing import Dict, Any, List
import requests
from tools import perform_rag_search, log_meal, create_diet, create_recipe, update_anamnesis, generate_menu_plan

SPRING_API_URL = os.getenv("SPRING_API_URL")

# Configuração do Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY não configurada no ambiente.")
    
genai.configure(api_key=GEMINI_API_KEY)

def clean_json_string(s):
    s = s.strip()
    if s.startswith("```json"):
        s = s[7:]
    if s.endswith("```"):
        s = s[:-3]
    s = s.strip()
    return s


async def run_orchestrator(
    pergunta: str, 
    image_data: str | None,
    full_context: str, 
    chat_history: List[str], 
    authorization_token: str,
    user_id: int,
    active_diet: Dict[str, Any] | None
) -> Dict[str, Any]:

    tools = [perform_rag_search, log_meal, create_diet, create_recipe, update_anamnesis, generate_menu_plan]

    tool_names = []
    for tool in tools:
        if hasattr(tool, 'name'):
            tool_names.append(tool.name)
        elif hasattr(tool, '__name__'):
            tool_names.append(tool.__name__)
        else:
            tool_names.append(str(tool))

    safety_settings = {
        genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
        genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
        genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
        genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
    }
    
    # --- MUDANÇA 1: PERSONALIDADE AJUSTADA E PROIBIÇÃO DE EMOJIS ---
    system_prompt = f"""
    Você é o NutriX, um assistente de IA nutricional avançado.
    Sua personalidade é estritamente PROFISSIONAL, CLÍNICA e OBJETIVA.
    Você deve agir como um nutricionista sério em um ambiente de consulta.

    --- REGRAS DE ESTILO (PRIORIDADE MÁXIMA) ---
    1. NÃO USE EMOJIS. Em nenhuma hipótese.
    2. Seja direto e baseie suas respostas em fatos e no contexto clínico do usuário.
    3. Evite gírias ou linguagem excessivamente casual. Mantenha a formalidade.

    --- DIRETRIZES DE SEGURANÇA E ESCOPO ---
    1. SEU PAPEL: Você é EXCLUSIVAMENTE um assistente de nutrição, saúde e bem-estar.
    2. RESTRIÇÃO DE TÓPICOS: RECUSE educadamente responder sobre qualquer assunto não relacionado a nutrição, saúde ou alimentação (ex: política, religião, programação, conhecimentos gerais fora da saúde, fofocas, etc.).
    3. EXEMPLO DE RECUSA: "Como assistente NutriX, meu foco restringe-se à sua nutrição e saúde clínica. Como posso auxiliar com seu plano alimentar?"
    
    --- MODO ANAMNESE (PRIORIDADE ALTA) ---
    Verifique o 'CONTEXTO DO USUÁRIO' abaixo.
    Se houver campos de saúde marcados como "N/A", null ou vazios, sua tarefa é completar a anamnese.
    NÃO responda perguntas gerais até que a anamnese básica esteja completa.
    
    FLUXO DE ANAMNESE:
    1. Identifique qual campo falta preencher na ordem abaixo.
    2. Faça Apenas UMA pergunta por vez referente a esse campo.
    3. Apresente as opções disponíveis (se houver) de forma clara.
    4. Quando o usuário responder, use a ferramenta `update_anamnesis` IMEDIATAMENTE.
    
    MAPA DE CAMPOS E VALORES (Use o valor em MAIÚSCULO na ferramenta):
    
    1. Motivo (mainGoal):
       - Opções: Emagrecimento, Massa Muscular, Controle de diabetes, Reeducação alimentar, Performance.
       - Mapeamento: "Emagrecimento"->WEIGHT_LOSS, "Massa Muscular"->MUSCLE_GAIN, "Diabetes"->DIABETES_CONTROL, "Reeducação"->DIET_REEDUCATION, "Performance"->PHYSICAL_MENTAL_PERFORMANCE
       
    2. Atividade (activityType):
       - Opções: Sedentário, Caminhada, Musculação, Corrida, Crossfit, Natação, Luta, Outro.
       - Mapeamento: "Luta"->FIGHT, "Sedentário"->SEDENTARY, "Caminhada"->WALKING, "Musculação"->WEIGHT_TRAINING, "Corrida"->RUNNING, "Crossfit"->CROSSFIT, "Natação"->SWIMMING, "Outro"->OTHER
       
    3. Frequência Semanal (frequency):
       - Opções: Nenhuma vez, 1-2x, 3-4x, 5 ou mais vezes.
       - Mapeamento: "Nenhuma"->NONE, "1-2x"->ONE_2X_WEEK, "3-4x"->THREE_4X_WEEK, "5 ou mais vezes"->FIVE_X_OR_MORE
       
    4. Minutos por dia (activityMinutesPerDay):
       - Pergunte quantos minutos por treino (ex: 30, 60, 90). Envie apenas o número.
       
    5. Sono (sleepQuality):
       - Opções: Boa, Regular, Ruim.
       - Mapeamento: GOOD, REGULAR, BAD
       
    6. Acorda a noite (wakesDuringNight):
       - Opções: Não, Pelo menos 1x, Mais que 1x.
       - Mapeamento: "Não"->NO, "1x"->ONCE, "+1x"->MORE_THAN_ONCE
       
    7. Intestino (bowelFrequency):
       - Opções: Todo dia, 5x/sem, 3x/sem, 1x/sem.
       - Mapeamento: "Todo dia"->EVERY_DAY, "5x"->FIVE_X_WEEK, "3x"->THREE_X_WEEK, "1x"->ONE_X_WEEK
       
    8. Estresse (stressLevel):
       - Opções: Baixo, Moderado, Alto.
       - Mapeamento: LOW, MODERATE, HIGH
       
    9. Álcool (alcoholUse):
       - Opções: Não consome, Socialmente (1-2x), Frequente (3-4x), Diário.
       - Mapeamento: "Não"->DOES_NOT_CONSUME, "Social"->SOCIAL_1_2X_WEEK, "Frequente"->FREQUENT_3_4X_WEEK, "Diário"->DAILY_USE
       
    10. Fumar (smoking): "Sim"->true, "Não"->false
    
    11. Hidratação (hydrationLevel):
        - Opções: Menos de 1L, 1-2L, 2-3L, Mais de 3L.
        - Mapeamento: "<1L"->LESS_THAN_1L, "1-2L"->BETWEEN_1_2L, "2-3L"->BETWEEN_2_3L, ">3L"->MORE_THAN_3L
        
    12. Condições Médicas (medicalConditions):
        - Pergunte: "Você possui alguma condição como Diabetes, Hipertensão, Colesterol, etc?"
        - Envie o texto exato ou lista separada por ponto e vírgula (;).
        - IMPORTANTE: Se o usuário disser que NÃO TEM ou "Nenhuma", envie estritamente o valor "NONE".

        - Mapeie a resposta do usuário para as opções abaixo se aplicável:
        * Diabetes tipo 1
          * Diabetes tipo 2
          * Hipertensão arterial
          * Dislipidemia
          * Doença renal
          * Doença hepática
          * Gastrite / refluxo
          * Intestino preso / diarreia
          * Osteoporose
          * Doença cardiovascular
          * Câncer
          * Depressão / Ansiedade
          * Doenças autoimunes
        
    13. Alergias (allergies):
        - Pergunte: "Possui alguma alergia ou intolerância (ex: Lactose, Glúten)?"
        - IMPORTANTE: Se o usuário disser que NÃO TEM ou "Nenhuma", envie estritamente o valor "NONE".

        OPÇÕES VÁLIDAS:
        "Intolerância à lactose", "Sensibilidade ao glúten / doença celíaca", "Alergia alimentar", "Alergia medicamentosa".
        
    14. Cirurgias (surgeries):
        - Pergunte: "Já realizou alguma cirurgia (ex: Bariátrica, Vesícula)?"
        - IMPORTANTE: Se o usuário disser que NÃO TEM ou "Nenhuma", envie estritamente o valor "NONE".

        OPÇÕES VÁLIDAS:
        "Bariátrica", "Vesícula", "Hérnia de hiato", "Ortopédica", "Cesárea / Ginecológica".
        
    15. Medicação Contínua (continuousMedication): "Sim"->true, "Não"->false

    HISTÓRICO DA CONVERSA:
    {chat_history}

    CONTEXTO DO USUÁRIO (NÃO repita isso na resposta, use para informar):
    {full_context}

    REGRAS DE FERRAMENTAS:
    - Você tem acesso a estas ferramentas: {tool_names}.
    
    - **NÃO PERGUNTE ANTES DE USAR AS FERRAMENTAS.** Se a intenção do usuário
      corresponde a uma ferramenta, use-a DIRETAMENTE.
      
    - **perform_rag_search**: Use esta ferramenta para perguntas gerais sobre nutrição, dietas,
      condições médicas (como diabetes, hipertensão), alimentos, etc.
      
    - **log_meal**: Use esta ferramenta QUANDO e APENAS QUANDO o usuário registrar
      explicitamente o que comeu. Ex: "Hoje comi...", "Anote meu almoço: ..."
      **ATENÇÃO:** Se você receber uma IMAGEM de comida, analise-a visualmente, estime 
      as calorias e macronutrientes (Proteína, Carbo, Gordura) e chame `log_meal` 
      IMEDIATAMENTE com sua estimativa. Não peça confirmação, apenas registre.
      
    - **create_diet**: Use esta ferramenta DIRETAMENTE (sem perguntar) quando o usuário
      pedir para "criar uma dieta", "iniciar um plano alimentar", "fazer uma nova dieta", etc.
      Você DEVE extrair os parâmetros obrigatórios: 'title', 'endDate' (formato YYYO-DD-MM),
      e 'targetWeight' (em kg).
    - **NÃO use `create_diet` se o usuário já tiver uma dieta ativa** (o contexto informará). 
      Em vez disso, informe que ele já tem uma e pergunte se deseja cancelar a atual.
      
    - **create_recipe**: Use esta ferramenta DIRETAMENTE (sem perguntar) quando o usuário
      pedir para "criar uma receita", "me dê uma ideia de jantar", "sugira um prato", etc.
      Extraia a 'query' (o que ele quer) e 'constraints' (restrições como calorias, tempo).
      
    - Se a pergunta do usuário não se encaixa em nenhuma ferramenta,
      responda usando o CONTEXTO DO USUÁRIO e o HISTÓRICO.
    - Sempre responda em Português (Brasil).
    """

    # Inicializa o modelo (Flash é recomendado para Vision/Multimodal rápido)
    model = genai.GenerativeModel(
        model_name='gemini-2.5-flash', 
        system_instruction=system_prompt,
        tools=tools,
        safety_settings=safety_settings
    )

    text_generation_model = genai.GenerativeModel(
        model_name='gemini-2.5-flash'
    )
    
    # --- LÓGICA DE PREPARAÇÃO DA MENSAGEM (TEXTO + IMAGEM) ---
    msg_content = []
    if pergunta:
        msg_content.append(pergunta)
    
    if image_data:
        try:
            # Remove o cabeçalho do base64 se existir (ex: "data:image/png;base64,")
            if "base64," in image_data:
                image_data = image_data.split("base64,")[1]
            
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            msg_content.append(image)
            msg_content.append("\n[SISTEMA] O usuário enviou esta imagem. Se for comida, analise, estime calorias e chame log_meal.")
            print("--- Imagem processada e adicionada ao prompt ---")
        except Exception as e:
            print(f"Erro ao processar imagem: {e}")
            return {"resposta": f"Recebi a imagem, mas tive um erro ao processá-la: {e}", "meal_saved": False, "diet_created": False}

    convo = model.start_chat()
    
    try:
        # Se a lista estiver vazia (user mandou nada), coloca um fallback
        if not msg_content:
             msg_content = ["Olá"] 

        # O método send_message_async aceita uma lista mista [str, Image]
        response = await convo.send_message_async(msg_content)
        
        # Proteção contra resposta vazia
        if not response.parts:
            return {"resposta": "Desculpe, não consegui processar sua solicitação no momento (sem resposta da IA).", "meal_saved": False, "diet_created": False}
            
        response_content = response.parts[0]
        
    except Exception as e:
        print(f"Erro ao chamar o Gemini: {e}")
        return {"resposta": f"Desculpe, tive um problema ao processar sua solicitação: {e}", "meal_saved": False, "diet_created": False}

    final_result_json = {
        "resposta": "",
        "meal_saved": False,
        "diet_created": False
    }

    # --- TRATAMENTO DE CHAMADA DE FERRAMENTAS ---
    if response_content.function_call:
        function_call = response_content.function_call
        function_name = function_call.name
        function_args = {key: value for key, value in function_call.args.items()}

        tool_result_text = ""
        
        try:
            
            if function_name == "perform_rag_search":
                tool_result_text = perform_rag_search(function_args.get("query"))
            
            elif function_name == "log_meal":
                
                # --- MUDANÇA 2: Feedback Clínico ao Registrar Refeição ---
                description = function_args.get("description")
                
                payload = {
                    "type": function_args.get("type"),
                    "description": description,
                    "calories": function_args.get("calories"),
                    "protein": function_args.get("protein"),
                    "carbs": function_args.get("carbs"),
                    "fat": function_args.get("fat")
                }
                
                headers = {"Authorization": f"Bearer {authorization_token}"}
                url = f"{os.getenv('SPRING_API_URL')}/api/meals"
                
                try:
                    spring_response = requests.post(url, headers=headers, json=payload)
                    spring_response.raise_for_status() 
                    
                    # Logou com sucesso. Agora vamos gerar o feedback clínico.
                    tool_result_text = f"Refeição '{description}' registrada no sistema."
                    
                    prompt_feedback = f"""
                    Atue como um nutricionista clínico sério. O usuário acabou de consumir: "{description}".
                    
                    Analise este alimento considerando EXCLUSIVAMENTE o contexto de saúde abaixo:
                    {full_context}
                    
                    INSTRUÇÃO:
                    Forneça um feedback curto (máx 2 frases), profissional e sem emojis.
                    - Se o alimento for prejudicial para as condições do usuário (ex: açúcar para diabetes, sal para hipertensão, fast food), faça um ALERTA clínico educado.
                    - Se for uma boa escolha, faça um breve reforço positivo clínico.
                    - Se for neutro, apenas confirme o registro.
                    """
                    
                    try:
                        feedback_response = await text_generation_model.generate_content_async(prompt_feedback)
                        if feedback_response.parts:
                            clinical_feedback = feedback_response.text.strip()
                            tool_result_text += f"\n\nAnálise Clínica: {clinical_feedback}"
                    except Exception as ai_err:
                        print(f"Erro ao gerar feedback clínico: {ai_err}")
                        # Se falhar o feedback, não quebra o fluxo, apenas segue sem ele.

                    final_result_json['meal_saved'] = True
                    
                except requests.exceptions.HTTPError as http_err:
                    print(f"Erro HTTP ao salvar refeição: {http_err.response.text}")
                    tool_result_text = f"Erro ao salvar refeição: {http_err.response.text}"
                
            
            elif function_name == "create_diet":
                
                prompt_calculo = f"""
                Analise o seguinte contexto de usuário:
                {full_context}
                
                A meta é criar uma dieta para atingir {function_args.get('targetWeight')} kg até {function_args.get('endDate')}.
                
                Com base em todos os dados (idade, peso, altura, gênero, nível de atividade, objetivo), 
                calcule DUAS coisas:
                1.  'base_daily_calories': A meta de calorias diárias (ex: TMB * fator de atividade - déficit calórico).
                2.  'safe_metabolic_floor': O piso metabólico seguro (TMB ou um valor mínimo como 1200 kcal) 
                    abaixo do qual a IA nunca deve reajustar.
                
                Responda APENAS com um objeto JSON válido, sem explicações, markdown ou "```json".
                Exemplo:
                {{
                  "base_daily_calories": 1850,
                  "safe_metabolic_floor": 1400
                }}
                """
                
                print("--- Gerando cálculo de calorias ---")
                calc_response = await text_generation_model.generate_content_async(prompt_calculo)

                if not calc_response.parts:
                     raise Exception("IA de cálculo de dieta não retornou dados.")
                     
                cleaned_response = clean_json_string(calc_response.text)
                calorie_data = json.loads(cleaned_response)
                
                base_calories = calorie_data.get("base_daily_calories")
                safe_floor = calorie_data.get("safe_metabolic_floor")
                
                if not base_calories or not safe_floor:
                    raise Exception(f"IA falhou em calcular as calorias. Resposta: {cleaned_response}")

                print(f"--- Calorias calculadas: Base={base_calories}, Piso={safe_floor} ---")
                
                payload = {
                    "userId": user_id,
                    "title": function_args.get("title"),
                    "endDate": function_args.get("endDate"),
                    "targetWeight": function_args.get("targetWeight"),
                    "baseDailyCalories": base_calories,
                    "safeMetabolicFloor": safe_floor
                }
                
                headers = {"Authorization": f"Bearer {authorization_token}"}
                url = f"{os.getenv('SPRING_API_URL')}/api/diets"  

                try:
                    print(f"--- Enviando para o Spring: {url} ---")
                    spring_response = requests.post(url, headers=headers, json=payload)
                    spring_response.raise_for_status() 
                    
                    tool_result_text = (f"Dieta '{payload['title']}' criada com sucesso. "
                            f"Meta base definida: {base_calories} kcal/dia. "
                            f"O plano está disponível na seção 'Minha Dieta'.")
                    final_result_json['diet_created'] = True
                            
                except requests.exceptions.HTTPError as http_err:
                    print(f"Erro HTTP ao criar dieta: {http_err.response.text}")
                    tool_result_text = f"Erro ao salvar a dieta no backend: {http_err.response.text}"
                except Exception as e:
                    print(f"Erro geral ao criar dieta: {e}")
                    tool_result_text = f"Erro ao criar dieta: {e}"
            
            elif function_name == "create_recipe":
                print("--- 🧠 Orquestrador: Lógica 'create_recipe' ativada ---")
                
                recipe_query = function_args.get("query")
                recipe_constraints = function_args.get("constraints", "Nenhuma")

                prompt_receita = f"""
                Você é um Nutricionista-Chef Clínico.
                Sua tarefa é criar UMA receita com base no pedido do usuário e em seu contexto de saúde.
                CONTEXTO DE SAÚDE DO USUÁRIO (Use para restrições OBRIGATÓRIAS):
                {full_context} 
                (Preste atenção especial a: 'medicalConditions', 'allergies', 'mainGoal')
                PEDIDO DO USUÁRIO:
                - Descrição: {recipe_query}
                - Restrições Adicionais: {recipe_constraints}
                INSTRUÇÕES:
                1.  Crie uma receita que se alinhe ao PEDIDO e ao CONTEXTO de saúde (alergias, etc.).
                2.  Calcule as estimativas nutricionais (calorias, proteína, carboidratos, gordura).
                3.  Responda APENAS com um objeto JSON válido. Não inclua "```json" ou explicações.
                4.  NÃO use emojis.
                FORMATO JSON OBRIGATÓRIAS:
                ... (formato JSON) ...
                """

                print("--- Gerando receita (sub-chamada da IA) ---")
                recipe_response = await text_generation_model.generate_content_async(prompt_receita)
                
                if not recipe_response.parts:
                     raise Exception("IA de receita não retornou dados.")

                cleaned_response = clean_json_string(recipe_response.text)
                
                try:
                    recipe_data = json.loads(cleaned_response)
                except json.JSONDecodeError:
                    raise Exception(f"Sub-IA de receita falhou em retornar um JSON. Resposta: {cleaned_response}")

                ingredientes_lista = []
                for item in recipe_data.get('ingredients', []):
                    if isinstance(item, dict):
                        amount = item.get('amount', 'A gosto')
                        name = item.get('name', 'Ingrediente')
                        ingredientes_lista.append(f"- {amount} de {name}")
                    elif isinstance(item, str):
                        ingredientes_lista.append(f"- {item}")

                passos_lista = []
                for i, passo in enumerate(recipe_data.get('instructions', [])):
                    if isinstance(passo, str):
                        passos_lista.append(f"{i+1}. {passo}")

                if not ingredientes_lista or not passos_lista:
                    raise Exception(f"A sub-IA retornou um JSON, mas ele estava vazio ou malformado. Resposta: {cleaned_response}")

                ingredientes_str = "\n".join(ingredientes_lista)
                passos_str = "\n".join(passos_lista)

                tool_result_text = f"""
                Receita gerada:
                - Título: {recipe_data.get('title', 'N/A')}
                - Descrição: {recipe_data.get('description', 'N/A')}
                - Calorias: {recipe_data.get('calories', 0)} kcal
                - Proteína: {recipe_data.get('protein', 0)} g
                - Carboidratos: {recipe_data.get('carbs', 0)} g
                - Gordura: {recipe_data.get('fat', 0)} g
                
                Ingredientes:
                {ingredientes_str}

                Modo de Preparo:
                {passos_str}
                """
            
            elif function_name == "update_anamnesis":
                field = function_args.get("field")
                value = function_args.get("value")
                
                payload = {"field": field, "value": str(value)}
                headers = {"Authorization": f"Bearer {authorization_token}"}
                url = f"{os.getenv('SPRING_API_URL')}/api/anamnesis/{user_id}/partial"
                
                try:
                    spring_response = requests.patch(url, headers=headers, json=payload)
                    spring_response.raise_for_status()
                    tool_result_text = f"Campo '{field}' atualizado para '{value}'. Prossiga."
                except Exception as e:
                    tool_result_text = f"Erro ao salvar anamnese: {e}"

            elif function_name == "generate_menu_plan":
                        if not active_diet:
                            tool_result_text = "Erro: O usuário não possui uma dieta ativa para gerar cardápios."
                        else:
                            days_to_gen = int(function_args.get("days", 3))
                            targets = active_diet.get('dailyTargets', [])
                            targets.sort(key=lambda x: x['targetDate'])
                            
                            import datetime
                            today = datetime.date.today().isoformat()
                            upcoming = [t for t in targets if t['targetDate'] >= today][:days_to_gen]
                            
                            if not upcoming:
                                tool_result_text = "Não há metas futuras na dieta ativa para gerar cardápio."
                            else:
                                success_count = 0
                                
                                for day in upcoming:
                                    prompt_menu = f"""
                                    Atue como Nutricionista Esportivo Clínico.
                                    Gere um cardápio diário completo (Café, Almoço, Jantar, Lanches) para esta data: {day['targetDate']}.
                                    
                                    CONTEXTO DO USUÁRIO:
                                    {full_context}
                                    
                                    META DO DIA:
                                    - Calorias: {day['adjustedCalories']} kcal
                                    - Proteína: {day.get('adjustedProteinG', 'N/A')}g
                                    - Carbo: {day.get('adjustedCarbsG', 'N/A')}g
                                    - Gordura: {day.get('adjustedFatsG', 'N/A')}g
                                    
                                    REGRAS:
                                    - Respeite estritamente as alergias e preferências.
                                    - Use alimentos acessíveis no Brasil.
                                    - Seja direto, prático e clínico.
                                    - NÃO USE EMOJIS.
                                    - Formate de forma limpa para leitura (use listas markdown).
                                    - NÃO responda com JSON, responda com o TEXTO FINAL.
                                    """
                                    
                                    print(f"--- Gerando cardápio para {day['targetDate']}... ---")
                                    menu_response = await text_generation_model.generate_content_async(prompt_menu)
                                    
                                    if menu_response.parts:
                                        menu_text = menu_response.text.strip()
                                        
                                        url = f"{os.getenv('SPRING_API_URL')}/api/diets/daily/{day['id']}"
                                        payload = {"suggestedMenu": menu_text}
                                        headers = {"Authorization": f"Bearer {authorization_token}"}
                                        
                                        try:
                                            requests.put(url, json=payload, headers=headers)
                                            success_count += 1
                                        except Exception as e:
                                            print(f"Erro ao salvar menu do dia {day['targetDate']}: {e}")
                                    else:
                                        print(f"Erro: IA não gerou cardápio para {day['targetDate']}")

                                tool_result_text = f"Sucesso. Gere cardápios detalhados para os próximos {success_count} dias. Disponível na tela de Dieta."
            
            else:
                tool_result_text = f"Erro: Ferramenta '{function_name}' desconhecida."
            
            content_to_send = {
                "function_response": {
                    "name": function_name,
                    "response": {"result": tool_result_text},
                }
            }
            
            response = await convo.send_message_async(content_to_send)

            if response.parts:
                final_result_json['resposta'] = response.text 
            else:
                final_result_json['resposta'] = f"A ferramenta {function_name} foi processada. Resultado: {tool_result_text}"

            
        except Exception as e:
            print(f"Erro ao executar a ferramenta {function_name}: {e}")
            final_result_json['resposta'] = f"Desculpe, erro ao usar ferramenta {function_name}: {e}"

    else:
        final_result_json['resposta'] = response_content.text

    return final_result_json