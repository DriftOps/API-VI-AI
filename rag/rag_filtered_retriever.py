import re
from rag.rag_retriever import retrieve_documents

def retrieve_filtered_documents(collection, pergunta, topico_nutricional=None):
    """
    Recupera documentos filtrando por tópico nutricional
    """
    # Primeiro, recupera documentos normalmente
    docs = retrieve_documents(collection, pergunta)
    
    # Define termos por tópico
    topicos = {
        "cafe_manha": ["café da manhã", "desjejum", "matinal", "manhã", "ovo", "pão", "fruta", "cereal", "aveia", "iogurte"],
        "almoco": ["almoço", "almoçar", "refeição principal", "proteína", "carboidrato", "arroz", "feijão", "salada"],
        "jantar": ["jantar", "ceia", "noturno", "leve", "sopa", "salada"],
        "lanche": ["lanche", "merenda", "intervalo", "snack", "fruta", "castanha"]
    }
    
    # Detecta tópico da pergunta
    pergunta_lower = pergunta.lower()
    tópico_detectado = None
    
    for topico, termos in topicos.items():
        if any(termo in pergunta_lower for termo in termos):
            tópico_detectado = topico
            break
    
    print(f"🎯 Tópico detectado: {tópico_detectado}")
    
    # Filtra documentos por relevância
    docs_filtrados = []
    for doc in docs:
        doc_lower = doc.lower()
        
        # Se detectou tópico, filtra por ele
        if tópico_detectado and any(termo in doc_lower for termo in topicos[tópico_detectado]):
            docs_filtrados.append(doc)
        # Se não detectou tópico específico, mantém todos
        elif not tópico_detectado:
            docs_filtrados.append(doc)
    
    # Se filtrou tudo, volta alguns documentos
    if not docs_filtrados and docs:
        docs_filtrados = docs[:2]  # Pega os 2 mais relevantes
    
    print(f"📊 Documentos após filtro: {len(docs_filtrados)}")
    return docs_filtrados