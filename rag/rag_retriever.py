# rag_retriever.py
from langchain.vectorstores import Chroma

def create_retriever(collection):
    # Usa o mesmo client do Chroma
    vectorstore = Chroma(collection_name=collection.name, client=collection._client)
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 3}  # retorna 3 documentos mais relevantes
    )
    return retriever
