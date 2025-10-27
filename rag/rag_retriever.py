def retrieve_documents(collection, pergunta: str, score_threshold=0.45, max_docs=5, max_chunk_size=1500):
    results = collection.query(
        query_texts=[pergunta],
        n_results=max_docs,
        include=["documents", "distances"]
    )
    
    docs = results.get("documents", [[]])[0]
    scores = results.get("distances", [[]])[0]  # quanto menor, melhor
    
    filtered_docs = []
    for doc, score in zip(docs, scores):
        if score <= score_threshold:
            # reduz chunk gigante (ajuda o LLM focar)
            if len(doc) > max_chunk_size:
                doc = doc[:max_chunk_size] + "..."
            filtered_docs.append(doc)

    return filtered_docs