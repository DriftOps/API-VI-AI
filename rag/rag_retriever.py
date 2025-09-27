def retrieve_documents(collection, pergunta: str):
    # Faz a busca de similaridade diretamente
    results = collection.query(
        query_texts=[pergunta],
        n_results=3  # k=3 documentos mais relevantes
    )
    
    # Extrai o conteúdo dos documentos
    documents = results.get("documents", [[]])[0]
    
    # Retorna uma lista simples de strings de documentos
    return documents