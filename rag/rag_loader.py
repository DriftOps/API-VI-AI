# rag_loader.py
import os
import pandas as pd
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

load_dotenv()

def load_csv_to_chroma(csv_files, collection_name="nutrientes_collection"):
    # Cria client local
    client = chromadb.Client()
    
    # Embedding usando OpenAI (ou substitua por Gemini se suportado)
    embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv("GEMINI_API_KEY"),
        model_name="text-embedding-3-small"
    )
    
    # Checa se a collection existe
    if collection_name in [c.name for c in client.list_collections()]:
        collection = client.get_collection(name=collection_name)
    else:
        collection = client.create_collection(
            name=collection_name,
            embedding_function=embedding_fn
        )
    
    # Carrega CSVs
    for file in csv_files:
        df = pd.read_csv(file)
        for idx, row in df.iterrows():
            collection.upsert(
                ids=[str(row["id"])],
                documents=[row["text"]],
                metadatas=[{"source": file}]
            )
    return collection
