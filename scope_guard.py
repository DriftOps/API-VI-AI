import logging

# Configura logging simples
logging.basicConfig(
    filename="rag_guard.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Tópicos permitidos
ALLOWED_TOPICS = [
    "proteína", "vitamina", "calorias", "minerais", "fibras",
    "nutrição", "água", "hidratação", "carboidratos", "gorduras"
]

# Palavras proibidas / fora do escopo
PROIBIDO = ["medicina", "diagnóstico", "legal", "finanças", "remédio"]

def compress_docs(docs, top_n=3):
    """Remove duplicados e limita top N documentos"""
    seen = set()
    compressed = []
    for doc in docs:
        if doc not in seen:
            compressed.append(doc)
            seen.add(doc)
    return compressed[:top_n]

def check_scope(pergunta):
    """Verifica se a pergunta está dentro do escopo permitido"""
    pergunta_lower = pergunta.lower()
    if not any(topic in pergunta_lower for topic in ALLOWED_TOPICS):
        return False
    return True

def filter_response(response_text):
    """Verifica se a resposta contém palavras proibidas"""
    resp_lower = response_text.lower()
    if any(word in resp_lower for word in PROIBIDO):
        return "Não posso responder a perguntas fora do escopo de nutrição."
    return response_text

def log_interaction(pergunta, docs, resposta):
    """Registra pergunta, documentos usados e resposta final"""
    logging.info("Pergunta: %s", pergunta)
    logging.info("Docs usados: %s", docs)
    logging.info("Resposta: %s", resposta)

def guarded_rag_response(gemini_model, pergunta, docs):
    """Função principal para usar RAG com guardrails"""
    # Checa escopo
    if not check_scope(pergunta):
        resposta = "Pergunta fora do escopo de nutrição."
        log_interaction(pergunta, docs, resposta)
        return resposta

    # Comprime docs
    docs = compress_docs(docs)
    if not docs:
        resposta = "Não há dados suficientes para responder.\nFontes:\n- Nenhuma disponível"
        log_interaction(pergunta, docs, resposta)
        return resposta

    contexto = "\n".join(docs)
    prompt = f"""
Instruções para a IA:
- Responda apenas baseado nas informações abaixo.
- Cite a fonte.
- Se não houver informação, diga que não sabe.
- Nunca invente dados.

Contexto:
{contexto}

Pergunta:
{pergunta}
"""

    # Gera resposta com temperatura baixa para evitar alucinação
    response = gemini_model.generate_content(
        prompt,
        temperature=0.2,
        max_output_tokens=200
    )

    # Aplica filtro de palavras proibidas
    resposta_final = filter_response(response.text)

    # Loga tudo
    log_interaction(pergunta, docs, resposta_final)

    return resposta_final
