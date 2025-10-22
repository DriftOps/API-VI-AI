# app.py
import os, sqlite3, json, time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import google.generativeai as genai

# Carrega variáveis do .env
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("Defina GEMINI_API_KEY no .env")

# Chave da API do Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Cria o modelo e exporta
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

DB = "nutrix.db"
app = FastAPI()

# --------- Models ---------
class MessageIn(BaseModel):
    external_user_id: str
    text: str
    user_meta: dict | None = None  # ex: {"weight":80, "goal":"emagrecer"}

# --------- DB helpers ---------
def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_schema():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(open("schema.sql").read())
    conn.commit()
    conn.close()

def get_or_create_user(external_id, user_meta=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE external_id = ?", (external_id,))
    row = cur.fetchone()
    if row:
        conn.close()
        return row
    # criar user básico
    name = user_meta.get("name") if user_meta else None
    age = user_meta.get("age") if user_meta else None
    weight = user_meta.get("weight") if user_meta else None
    goal = user_meta.get("goal") if user_meta else None
    cur.execute("INSERT INTO users(external_id, name, age, weight, goal, restrictions) VALUES (?,?,?,?,?,?)",
                (external_id, name, age, weight, goal, json.dumps(user_meta.get("restrictions") if user_meta else None)))
    conn.commit()
    cur.execute("SELECT * FROM users WHERE external_id = ?", (external_id,))
    row = cur.fetchone()
    conn.close()
    return row

def save_history(user_id, role, content, meta=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO history(user_id, role, content, meta) VALUES (?,?,?,?)",
                (user_id, role, content, json.dumps(meta) if meta else None))
    conn.commit()
    conn.close()

def load_recent_history(user_id, limit=8):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT role, content, meta, created_at FROM history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit))
    rows = cur.fetchall()
    conn.close()
    # inverter pra ordem cronológica
    return [dict(r) for r in reversed(rows)]

# --------- Prompt builder ---------
def build_prompt(user_row, recent_history, user_message):
    profile = {
        "name": user_row["name"],
        "age": user_row["age"],
        "weight": user_row["weight"],
        "goal": user_row["goal"],
        "restrictions": json.loads(user_row["restrictions"]) if user_row["restrictions"] else None
    }
    system = (
        "Você é NutriX, um assistente de nutrição prático, direto, breve e amigável. "
        "Responda no máximo em 6 parágrafos curtos. Se o usuário pedir plano, gere macros aproximados."
    )
    # montar conversa com histórico
    convo = system + "\n\nPerfil do usuário:\n" + json.dumps(profile, ensure_ascii=False) + "\n\nHistórico:\n"
    for h in recent_history:
        convo += f"{h['role'].upper()}: {h['content']}\n"
    convo += f"USER: {user_message}\nASSISTANT:"
    return convo

# --------- Gemini call (exemplo genérico) ---------
def call_gemini(prompt):
    model = genai.GenerativeModel(
        model_name="models/gemini-2.5-flash",
        system_instruction="Você é NutriX, ... (resumo curto do comportamento)"
    )
    # chamada simples
    resp = model.generate_text(prompt=prompt, max_output_tokens=512)
    # dependendo da lib, ajuste
    return resp.text if hasattr(resp, "text") else str(resp)

# --------- Endpoint principal ---------
@app.post("/message")
def handle_message(msg: MessageIn):
    user_row = get_or_create_user(msg.external_user_id, msg.user_meta)
    user_id = user_row["id"]
    # salvar a mensagem do usuário
    save_history(user_id, "user", msg.text, meta=msg.user_meta)
    # carregar histórico recente
    recent = load_recent_history(user_id, limit=8)
    prompt = build_prompt(user_row, recent, msg.text)
    # chamar o modelo
    try:
        assistant_text = call_gemini(prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    # salvar resposta
    save_history(user_id, "assistant", assistant_text)
    return {"reply": assistant_text}