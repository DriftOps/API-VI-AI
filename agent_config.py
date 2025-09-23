import os
from dotenv import load_dotenv
import google.generativeai as genai
from google.adk.agents import Agent

# Carregar variáveis do .env
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("Defina a variável GEMINI_API_KEY no seu arquivo .env")

# Configurar Gemini
genai.configure(api_key=GEMINI_API_KEY)


#modelo
gemini_model = genai.GenerativeModel("gemini-1.5-flash")


#agente adk
root_agent = Agent(
    model="gemini-1.5-flash",
    name="NutriX",
    instruction="""
        Você é um assistente especializado em nutrição.
        Responda de forma clara, prática e amigável.
        Base inicial:
        - Frutas e vegetais são ricos em vitaminas e fibras.
        - Proteínas ajudam na construção muscular e saciedade.
        - Água é essencial para hidratação.
        - Evitar excesso de açúcar e alimentos ultraprocessados é saudável.
        - Uma alimentação equilibrada inclui carboidratos, proteínas, gorduras saudáveis, vitaminas e minerais.
    """
)
