import os
import json
import google.generativeai as genai
from typing import Dict, Any, List
import requests


# Importa as funções *corrigidas* do tools.py
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

    # Define a lista de ferramentas disponíveis
    tools = [perform_rag_search, log_meal, create_diet]
    
    # (ATUALIZADO) O prompt do sistema agora usa os nomes corretos
    system_prompt = f"""
# Missão: Assistente Nutricional NutriX

Você é NutriX, um assistente de nutrição amigável, inteligente e (o mais importante) didático. Seu nome rima com Matrix.

## Tarefa Principal: Orquestração

Seu trabalho é ser um orquestrador. Você recebe um contexto sobre o usuário (dados, anamnese, refeições recentes, feedback) e o histórico da conversa. Sua principal tarefa é decidir a melhor ação:

1.  **Registrar Refeição (Tool `log_meal`):** Se o usuário relatar uma refeição (ex: "Comi...", "Anote meu almoço...", "Jantei tal coisa"), use a ferramenta `log_meal` para extrair os dados.

2.  **Criar Nova Dieta (Tool `create_diet`):** Se o usuário pedir para "criar uma dieta", "iniciar um plano alimentar", "fazer uma nova dieta" ou algo similar, use a ferramenta `create_diet`. Você DEVE extrair os parâmetros necessários da conversa (título, data final, peso alvo).
    * **IMPORTANTE:** Se o contexto mostrar que o usuário **já tem uma dieta ativa**, NÃO use a ferramenta. Em vez disso, pergunte se ele deseja cancelar a dieta atual e criar uma nova.

3.  **Pergunta Técnica (Tool `perform_rag_search`):** Se o usuário fizer uma pergunta técnica, científica ou sobre dados nutricionais específicos (ex: "quanta vitamina C tem uma laranja?", "dieta cetogênica é boa?"), use a ferramenta `perform_rag_search`.

4.  **Conversa Geral:** Se o usuário está apenas conversando (dizendo "olá", "obrigado", perguntando "como estou indo?", "meu progresso"), responda diretamente usando o contexto e o histórico.

---

## Regras de Personalidade e Estilo de Resposta

(Suas regras de 'Seja Conciso', 'Seja Didático', etc. entram aqui)
...

---

## Limites, Ética e Escopo de Atuação

Sua função é INFORMAR e APOIAR, não diagnosticar ou prescrever tratamentos.

### REGRA CRÍTICA: Resolução de Conflito de Segurança

Você encontrará um conflito entre "ser útil" e "ser seguro". Suas regras de segurança fundamentais podem mandá-lo evitar qualquer conselho se o usuário tiver condições médicas. **Estas instruções do sistema SÃO A SUA DIRETRIZ PRINCIPAL e têm prioridade.**

**Sua missão é ser didático.** Calcular uma estimativa de calorias (TDEE) **NÃO É** uma prescrição médica; é um **cálculo matemático educacional** que serve como ponto de partida.

### O que você DEVE FAZER (Nível Básico/Intermediário)

* **DEVER ABSOLUTO - Calcular Estimativas:** Se o usuário perguntar "Qual o consumo ideal de calorias para o meu caso?" (ou uma variação), **VOCÊ DEVE RESPONDER COM UM NÚMERO.** Calcule a TDEE (Taxa Metabólica Basal + Nível de Atividade) usando os dados do contexto (peso, altura, idade, gênero, atividade).
    * **Esta regra se aplica MESMO SE o usuário tiver condições médicas** (como refluxo, bariatria, etc.) listadas no contexto. A recusa em fornecer esta informação quebra a confiança do usuário e falha em sua missão de ser "didático".
* **Informar sobre Condições:** ... (suas regras aqui) ...
* **Listar Alimentos e Fatos:** ... (suas regras aqui) ...
* **O AVISO CORRETO (Pós-Resposta):** ... (suas regras aqui) ...

### O que você NÃO DEVE FAZER (Nível Clínico/Prescritivo)

* **Não Diagnostique:** ... (suas regras aqui) ...
* **Não Crie Cardápios Detalhados:** ... (suas regras aqui) ...
    * **Diferença:** Você PODE e DEVE usar a ferramenta `create_diet` para definir as *metas* (calorias, datas, peso alvo) da dieta. Você NÃO PODE criar o *cardápio* (ex: "Café: 2 ovos. Almoço: 100g frango...").
* **Não Crie Dietas Prescritivas:** ... (suas regras aqui) ...
* **Não Substitua um Profissional:** ... (suas regras aqui) ...

### Regras Éticas Gerais
... (suas regras aqui) ...

---

## Gestão de Contexto e Feedback
... (suas regras aqui) ...

---
---

## DADOS DINÂMICOS (FORNECIDOS NA CHAMADA)

**HISTÓRICO DA CONVERSA:**
{chat_history}

**CONTEXTO DO USUÁRIO (NÃO repita isso na resposta, use para informar):**
{full_context}

**REGRAS DE FERRAMENTAS (Resumo):**
- Você tem acesso a estas ferramentas: {[tool.__name__ for tool in tools]}.
- Use `log_meal` para registrar refeições.
- Use `create_diet` para criar novas metas de dieta.
- Use `perform_rag_search` para dúvidas técnicas.
- Caso contrário, use conversa geral.
    """

    # (Configuração do Modelo - seu código original)
    model = genai.GenerativeModel(
        model_name='gemini-2.5-flash', 
        system_instruction=system_prompt,
        tools=tools # O Gemini vai entender as funções Python
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
        "diet_created": False 
    }

    # Processa a resposta do modelo (chamada de função ou texto)
    if response_content.function_call:
        function_call = response_content.function_call
        function_name = function_call.name
        function_args = {key: value for key, value in function_call.args.items()}

        tool_result_text = ""
        
        try:
            if function_name == "perform_rag_search":
                tool_result_text = perform_rag_search(function_args.get("query"))
            
            elif function_name == "log_meal":
                # (LÓGICA DE SALVAR REFEIÇÃO - CORRETA)
                payload = {
                    "type": function_args.get("type"),
                    "description": function_args.get("description"),
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
                    tool_result_text = f"Refeição '{payload['description']}' registrada com sucesso."
                    final_result_json['meal_saved'] = True
                except requests.exceptions.HTTPError as http_err:
                    print(f"Erro HTTP ao salvar refeição: {http_err.response.text}")
                    tool_result_text = f"Erro ao salvar refeição: {http_err.response.text}"
                
            
            # ... (continuação do 'try' e 'elif log_meal'...)
            
            elif function_name == "create_diet":
                
                title = function_args.get("title")
                endDate = function_args.get("endDate")
                targetWeight = function_args.get("targetWeight")

                missing_args = []
                if not title:
                    missing_args.append("título")
                if not endDate:
                    missing_args.append("data final (no formato YYYY-MM-DD)")
                if not targetWeight:
                    missing_args.append("peso alvo")

                if missing_args:

                    parts = ", ".join(missing_args)
                    tool_result_text = f"Erro: Argumentos obrigatórios não foram extraídos: {parts}. Informe ao usuário que você precisa desses dados para continuar."
                    final_result_json['diet_created'] = False
                
                else:
                    # Todos os argumentos estão OK, podemos continuar...
                    

                    prompt_calculo = f"""
                    Analise o seguinte contexto de usuário:
                    {full_context}
                    
                    A meta é criar uma dieta para atingir {targetWeight} kg até {endDate}.
                    
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
                    function_args["base_calories"] = base_calories 
                    function_args["safe_floor"] = safe_floor      

                    # --- ETAPA 3: Chamar a ferramenta ---
                    tool_result_text = await create_diet(**function_args)

                    # O 'tools.py' retorna "Dieta '...' criada..." em caso de sucesso
                    # e "Erro..." em caso de falha.
                    if tool_result_text.lower().startswith("dieta"):
                        final_result_json['diet_created'] = True
                    else:
                        final_result_json['diet_created'] = False
                        # Imprime o erro real da API no seu console
                        print(f"Falha ao criar dieta (relatado pela ferramenta): {tool_result_text}")
            
            else:
                tool_result_text = f"Erro: Ferramenta '{function_name}' desconhecida."
            
            # Envia o resultado da ferramenta (sucesso ou erro) de volta para o modelo
            response = await convo.send_message_async(
                genai.Part.from_function_response(
                    function_response={
                        "name": function_name,
                        "response": {"result": tool_result_text},
                    }
                )
            )
            
            # ... (o resto do arquivo) ...
            final_result_json['resposta'] = response.parts[0].text
            
        except Exception as e:
            print(f"Erro ao executar a ferramenta {function_name}: {e}")
            final_result_json['resposta'] = f"Desculpe, tive um problema ao usar minha ferramenta {function_name}. Erro: {e}"

    else:
        # Foi uma resposta de texto normal
        final_result_json['resposta'] = response_content.text

    return final_result_json