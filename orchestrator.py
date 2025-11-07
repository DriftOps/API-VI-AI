# orchestrator.py
import os
import json
import google.generativeai as genai
from typing import Dict, Any, List

# (CORRIGIDO) Importa os nomes corretos do seu tools.py
from tools import perform_rag_search, log_meal, create_diet 

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
    user_id: int,                 # (Recebido de routes.py)
    active_diet: Dict[str, Any] | None # (Recebido de routes.py)
) -> Dict[str, Any]:

    # (CORRIGIDO) Define a lista de ferramentas disponíveis com os nomes corretos
    tools = [perform_rag_search, log_meal, create_diet]
    
    # (ATUALIZADO) O prompt do sistema agora usa os nomes corretos
    system_prompt = f"""
    Você é o NutriX, um assistente de IA nutricional avançado.
    Sua personalidade é amigável, encorajadora e profissional.
    Seu objetivo é ajudar o usuário a atingir suas metas de saúde.

    HISTÓRICO DA CONVERSA:
    {chat_history}

    CONTEXTO DO USUÁRIO (NÃO repita isso na resposta, use para informar):
    {full_context}

    REGRAS DE FERRAMENTAS:
    - Você tem acesso a estas ferramentas: {[tool.name for tool in tools]}.
    - **perform_rag_search**: Use esta ferramenta para perguntas gerais sobre nutrição, dietas,
      condições médicas (como diabetes, hipertensão), alimentos, etc.
    - **log_meal**: Use esta ferramenta QUANDO e APENAS QUANDO o usuário registrar
      explicitamente o que comeu. Ex: "Hoje comi...", "Anote meu almoço: ..."
    - **create_diet**: [NOVO] Use esta ferramenta quando o usuário pedir para "criar uma dieta",
      "iniciar um plano alimentar", "fazer uma nova dieta", etc.
      Você DEVE extrair os parâmetros obrigatórios: 'title', 'endDate' (formato YYYY-MM-DD),
      e 'targetWeight' (em kg).
    - **NÃO use `create_diet` se o usuário já tiver uma dieta ativa** (o contexto informará). 
      Em vez disso, pergunte se ele deseja cancelar a dieta atual e criar uma nova.
    - Se a pergunta do usuário não se encaixa em nenhuma ferramenta,
      responda usando o CONTEXTO DO USUÁRIO e o HISTÓRICO.
    - Sempre responda em Português (Brasil).
    """

    # (Configuração do Modelo - seu código original)
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash', # (Use 1.5-flash ou 1.5-pro)
        system_instruction=system_prompt,
        tools=tools
    )
    
    convo = model.start_chat()
    
    # Envia a pergunta do usuário para o modelo
    try:
        response = await convo.send_message_async(pergunta)
        response_content = response.parts[0]
    except Exception as e:
        print(f"Erro ao chamar o Gemini: {e}")
        return {"resposta": f"Desculpe, tive um problema ao processar sua solicitação: {e}", "meal_saved": False, "diet_created": False}

    # Inicializa o resultado padrão
    final_result_json = {
        "resposta": "",
        "meal_saved": False,
        "diet_created": False # (NOVO)
    }

    # Processa a resposta do modelo (chamada de função ou texto)
    if response_content.function_call:
        function_call = response_content.function_call
        function_name = function_call.name
        function_args = {key: value for key, value in function_call.args.items()}

        tool_result_text = ""
        
        try:
            # (CORRIGIDO) Chama as ferramentas com os nomes corretos
            
            if function_name == "perform_rag_search":
                # (Seu 'tools.py' espera 'query' como argumento)
                tool_result_text = perform_rag_search(function_args.get("query"))
            
            elif function_name == "log_meal":
                # (NOVO) A ferramenta 'log_meal' no seu tools.py só retorna um dict.
                # A LÓGICA DE API CALL DEVE VIVER AQUI.
                
                # 1. Prepara o payload
                payload = {
                    "type": function_args.get("type"),
                    "description": function_args.get("description"),
                    "calories": function_args.get("calories"),
                    "protein": function_args.get("protein"),
                    "carbs": function_args.get("carbs"),
                    "fat": function_args.get("fat")
                }
                
                # 2. Faz a chamada de API
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
                # (LÓGICA DE CÁLCULO MOVIDA PARA CÁ)
                
                # --- ETAPA 1: Chamar a IA para calcular calorias ---
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
                # (Usa o mesmo modelo 'model' para a sub-chamada)
                calc_response = await model.generate_content_async(prompt_calculo)
                
                cleaned_response = clean_json_string(calc_response.text)
                calorie_data = json.loads(cleaned_response)
                
                base_calories = calorie_data.get("base_daily_calories")
                safe_floor = calorie_data.get("safe_metabolic_floor")
                
                if not base_calories or not safe_floor:
                    raise Exception(f"IA falhou em calcular as calorias. Resposta: {cleaned_response}")

                print(f"--- Calorias calculadas: Base={base_calories}, Piso={safe_floor} ---")
                
                # --- ETAPA 2: Adiciona os argumentos calculados ---
                function_args["user_id"] = user_id
                function_args["token"] = authorization_token
                function_args["base_calories"] = base_calories # (NOVO)
                function_args["safe_floor"] = safe_floor       # (NOVO)

                # (Chama a ferramenta 'create_diet' SIMPLIFICADA)
                tool_result_text = create_diet(**function_args)
                final_result_json['diet_created'] = True
            
            else:
                tool_result_text = f"Erro: Ferramenta '{function_name}' desconhecida."
            
            # Envia o resultado da ferramenta de volta para o modelo
            response = await convo.send_message_async(
                genai.Part(
                    function_response={
                        "name": function_name,
                        "response": {"result": tool_result_text},
                    }
                )
            )
            final_result_json['resposta'] = response.parts[0].text
            
        except Exception as e:
            print(f"Erro ao executar a ferramenta {function_name}: {e}")
            final_result_json['resposta'] = f"Desculpe, tive um problema ao usar minha ferramenta {function_name}. Erro: {e}"

    else:
        # Foi uma resposta de texto normal
        final_result_json['resposta'] = response_content.text

    return final_result_json