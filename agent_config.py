import os
from dotenv import load_dotenv
import google.generativeai as genai

# Carregar variáveis do .env
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("Defina a variável GEMINI_API_KEY no seu arquivo .env")

# Configurar Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Criar modelo
gemini_model = genai.GenerativeModel("gemini-1.5-flash")
