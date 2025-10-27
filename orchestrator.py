from agent_config import gemini_model
from tools import perform_rag_search, log_meal
import google.generativeai as genai
from google.generativeai import protos  # Esta importação está CORRETA
import requests
import os

SPRING_API_URL = os.getenv("SPRING_API_URL")

# Mapeamento de nome da ferramenta (string) para a função Python
tool_functions = {
    "perform_rag_search": perform_rag_search,
    "log_meal": log_meal, 
}

async def run_orchestrator(pergunta: str, full_context: str, chat_history: list, authorization_token: str):
    """
    Orquestra a conversa, decidindo se deve usar RAG, registrar refeição, ou apenas conversar.
    """
    
    # 1. Iniciar a sessão de chat com o histórico ATUAL
    gemini_history = []
    for i, line in enumerate(chat_history):
        role = "user" if i % 2 == 0 else "model" 
        content = line.split(": ", 1)[-1]
        gemini_history.append({'role': role, 'parts': [content]})

    chat_session = gemini_model.start_chat(history=gemini_history)

    # 2. Montar o prompt
    prompt = f"""
    CONTEXTO DO USUÁRIO E REFEIÇÕES RECENTES:
    ---
    {full_context}
    ---
    
    PERGUNTA DO USUÁRIO:
    {pergunta}
    """
    
    # 3. Enviar a mensagem para o Gemini
    response = chat_session.send_message(prompt)
    
    meal_saved = False
    
    # 4. Loop de Tool Calling Manual
    while response.candidates[0].content.parts[0].function_call:
        function_call = response.candidates[0].content.parts[0].function_call
        tool_name = function_call.name
        tool_args = dict(function_call.args)

        print(f"--- Orquestrador decidiu usar: {tool_name} ---")
        print(f"--- Argumentos: {tool_args} ---")

        if tool_name not in tool_functions:
            raise Exception(f"Ferramenta desconhecida: {tool_name}")

        # --- Lógica de Execução da Ferramenta ---
        
        # A variável 'function_response_data' será preenchida por qualquer ferramenta
        
        if tool_name == "perform_rag_search":
            # Executa a busca RAG e obtém o contexto
            function_response_data = tool_functions[tool_name](**tool_args)
        
        elif tool_name == "log_meal":
            # A IA *preparou* os dados. Agora NÓS fazemos o POST para o Spring.
            if authorization_token:
                try:
                    headers = {"Authorization": f"Bearer {authorization_token}"}
                    post_url = f"{SPRING_API_URL}/api/meals"
                    
                    meal_data = tool_functions[tool_name](**tool_args) 
                    
                    post_resp = requests.post(post_url, headers=headers, json=meal_data)
                    
                    if post_resp.status_code in [200, 201]:
                        meal_saved = True
                        function_response_data = {"status": "Refeição registrada com sucesso!"}
                    else:
                        print(f"⚠️ Erro ao salvar refeição no Spring: {post_resp.text}")
                        function_response_data = {"status": f"Erro ao salvar: {post_resp.text}"}
                except Exception as e:
                    print(f"⚠️ Erro no POST da refeição: {e}")
                    function_response_data = {"status": f"Erro interno ao salvar: {e}"}
            else:
                function_response_data = {"status": "Erro: Token de autorização não encontrado."}
        
        # ==================================================================
        # 5. Enviar a resposta da ferramenta de volta para o modelo
        #    (MOVIDO PARA FORA DO 'elif' E SINTAXE CORRIGIDA)
        # ==================================================================
        
        response = chat_session.send_message(
            # Esta é a sintaxe correta:
            protos.Part(
                function_response=protos.FunctionResponse(
                    name=tool_name,
                    response=function_response_data
                )
            )
        )
        # Fim do 'while' loop, o loop verificará 'response.candidates' novamente

    # 6. Resposta final (após o loop de ferramentas, ou se nenhuma ferramenta foi usada)
    final_response_text = response.text
    
    return {"resposta": final_response_text, "meal_saved": meal_saved}