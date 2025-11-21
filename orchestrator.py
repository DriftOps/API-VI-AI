import os
import json
import google.generativeai as genai
from typing import Dict, Any, List
import requests
from tools import perform_rag_search, log_meal, create_diet, create_recipe

SPRING_API_URL = os.getenv("SPRING_API_URL")

# (Configuração do Gemini - seu código original)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY não configurada no ambiente.")
    
genai.configure(api_key=GEMINI_API_KEY)

# (Seu código original de 'clean_json_string')
def clean_json_string(s):
    s = s.strip()
    if s.startswith("```json"):
        s = s[7:]
    if s.endswith("```"):
        s = s[:-3]
    s = s.strip()
    return s


# (ATUALIZADO) Assinatura da função principal
async def run_orchestrator(
    pergunta: str, 
    full_context: str, 
    chat_history: List[str], 
    authorization_token: str,
    user_id: int,                 
    active_diet: Dict[str, Any] | None

) -> Dict[str, Any]:

    

    tools = [perform_rag_search, log_meal, create_diet, create_recipe]

    tool_names = []
    for tool in tools:
        if hasattr(tool, 'name'):
            tool_names.append(tool.name)
        elif hasattr(tool, '__name__'):
            tool_names.append(tool.__name__)
        else:
            # Segurança: se não tiver nenhum dos dois, não quebra
            tool_names.append(str(tool))

    safety_settings = {
        genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
        genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
        genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
        genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
    }
    
    system_prompt = f"""
    Você é o NutriX, um assistente de IA nutricional avançado.
    Sua personalidade é amigável, encorajadora e profissional.
    Seu objetivo é ajudar o usuário a atingir suas metas de saúde.

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

    model = genai.GenerativeModel(
        model_name='gemini-2.5-flash',
        system_instruction=system_prompt,
        tools=tools,
        safety_settings=safety_settings
    )

    text_generation_model = genai.GenerativeModel(
        model_name='gemini-2.5-flash'
    )
    
    convo = model.start_chat()
    
    try:
        response = await convo.send_message_async(pergunta)
        response_content = response.parts[0]
    except Exception as e:
        print(f"Erro ao chamar o Gemini: {e}")
        return {"resposta": f"Desculpe, tive um problema ao processar sua solicitação: {e}", "meal_saved": False, "diet_created": False}

    final_result_json = {
        "resposta": "",
        "meal_saved": False,
        "diet_created": False # 
    }

    if response_content.function_call:
        function_call = response_content.function_call
        function_name = function_call.name
        function_args = {key: value for key, value in function_call.args.items()}

        tool_result_text = ""
        
        try:
            
            if function_name == "perform_rag_search":
                tool_result_text = perform_rag_search(function_args.get("query"))
            
            elif function_name == "log_meal":
                
                payload = {
                    "type": function_args.get("type"),
                    "description": function_args.get("description"),
                    "calories": function_args.get("calories"),
                    "protein": function_args.get("protein"),
                    "carbs": function_args.get("carbs"),
                    "fat": function_args.get("fat")
                }
                
                headers = {"Authorization": f"Bearer {authorization_token}"}
                url = f"{os.getenv('SPRING_API_URL')}/api/meals" # (Pega a URL do env)
                
                try:
                    spring_response = requests.post(url, headers=headers, json=payload)
                    spring_response.raise_for_status() # Lança erro se não for 2xx
                    tool_result_text = f"Refeição '{payload['description']}' registrada com sucesso."
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
                    spring_response.raise_for_status() # Lança erro se não for 2xx
                    
                    tool_result_text = (f"Dieta '{payload['title']}' criada com sucesso! "
                            f"Calculei uma meta base de {base_calories} kcal/dia. "
                            f"Vou reajustar isso dinamicamente. O usuário já pode ver o plano na tela 'Minha Dieta'.")
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
                Você é um Nutricionista-Chef.
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
                FORMATO JSON OBRIGATÓRIAS:
                ... (formato JSON) ...
                """

                print("--- Gerando receita (sub-chamada da IA) ---")
                recipe_response = await text_generation_model.generate_content_async(prompt_receita)                
                cleaned_response = clean_json_string(recipe_response.text)
                
                try:
                    recipe_data = json.loads(cleaned_response)
                except json.JSONDecodeError:
                    raise Exception(f"Sub-IA de receita falhou em retornar um JSON. Resposta: {cleaned_response}")

                ingredientes_lista = []
                # Usamos .get('ingredients', []) para o caso da chave 'ingredients' nem existir
                for item in recipe_data.get('ingredients', []):
                    if isinstance(item, dict):
                        # Usamos .get() com valores padrão para evitar KeyErrors
                        amount = item.get('amount', 'A gosto')
                        name = item.get('name', 'Ingrediente')
                        ingredientes_lista.append(f"- {amount} de {name}")
                    elif isinstance(item, str):
                        # Se a IA mandar só uma string (ex: "100g de Frango")
                        ingredientes_lista.append(f"- {item}")

                passos_lista = []
                for i, passo in enumerate(recipe_data.get('instructions', [])):
                    if isinstance(passo, str):
                        passos_lista.append(f"{i+1}. {passo}")

                # Se, no final, as listas estiverem vazias, é porque o JSON falhou
                if not ingredientes_lista or not passos_lista:
                    raise Exception(f"A sub-IA retornou um JSON, mas ele estava vazio ou malformado. Resposta: {cleaned_response}")

                ingredientes_str = "\n".join(ingredientes_lista)
                passos_str = "\n".join(passos_lista)

                tool_result_text = f"""
                Receita gerada com sucesso pela sub-IA:
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
            
            else:
                tool_result_text = f"Erro: Ferramenta '{function_name}' desconhecida."
            
            # Envia o resultado da ferramenta de volta para o modelo
            content_to_send = {
                "function_response": {
                    "name": function_name,
                    "response": {"result": tool_result_text},
                }
            }
            
            response = await convo.send_message_async(content_to_send)

            final_result_json['resposta'] = response.parts[0].text
            
        except Exception as e:
            print(f"Erro ao executar a ferramenta {function_name}: {e}")
            final_result_json['resposta'] = f"Desculpe, tive um problema ao usar minha ferramenta {function_name}. Erro: {e}"

    else:
        # Foi uma resposta de texto normal
        final_result_json['resposta'] = response_content.text

    return final_result_json