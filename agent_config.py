import os
from dotenv import load_dotenv
import google.generativeai as genai
from tools import perform_rag_search, log_meal # Importar as ferramentas

# Carregar variáveis do .env
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("Defina a variável GEMINI_API_KEY no seu arquivo .env")

# Configurar Gemini
genai.configure(api_key=GEMINI_API_KEY)

try:
    with open("instruction.md", "r", encoding="utf-8") as f:
        SYSTEM_INSTRUCTION = f.read()
except FileNotFoundError:
    print("ERRO CRÍTICO: Arquivo 'system_prompt.md' não encontrado.")
    print("Por favor, crie o arquivo com as instruções do sistema.")
    # Fallback muito simples apenas para não quebrar
    SYSTEM_INSTRUCTION = "Você é um assistente de nutrição." 

# --- [NOVO] Configurações de Geração (Temperatura, etc.) ---
# Aqui você controla a "criatividade" e o comprimento da resposta.
generation_config = {
    # 'temperature': Controla a aleatoriedade.
    # Valores mais baixos (ex: 0.3) = respostas mais diretas e consistentes (bom para fatos).
    # Valores mais altos (ex: 0.9) = respostas mais criativas.
    # Para um assistente didático, mas preciso, 0.7 é um bom começo.
    "temperature": 0.7, 
    
    # 'max_output_tokens': Controla o tamanho MÁXIMO da resposta.
    # Isso ajuda a forçar as "respostas mais curtas" que você pediu.
    # 8192 é o padrão, vamos reduzir bastante. Ajuste conforme necessário.
    "max_output_tokens": 2048, 
    
    # 'top_p': Outra forma de controlar a aleatoriedade. 1.0 é o padrão.
    "top_p": 1.0, 
    
    # 'top_k': Limita a seleção de tokens. 1 é o padrão.
    "top_k": 1,
}

# Definir as ferramentas que o modelo pode usar
agent_tools = [perform_rag_search, log_meal]

safety_settings = {
    genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
    genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
    genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
    genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
}

gemini_model = genai.GenerativeModel(

    model_name="models/gemini-2.5-flash",  

    system_instruction=SYSTEM_INSTRUCTION,
    
    generation_config=generation_config,
    
    tools=agent_tools,

    safety_settings=safety_settings
)