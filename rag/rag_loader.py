import os
import pandas as pd
import chromadb
from chromadb.utils.embedding_functions import GoogleGenerativeAiEmbeddingFunction
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHROMA_PATH = "chroma_db"

def load_csv_to_chroma(csv_files, collection_name="nutrientes_collection"):
    client = chromadb.PersistentClient(path="chroma_db")
    embedding_fn = GoogleGenerativeAiEmbeddingFunction(api_key=GEMINI_API_KEY, model_name="models/text-embedding-004")

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_fn
    )

    if collection.count() == 0:
        print("Collection is empty. Loading data from CSVs...")
        for file in csv_files:
            try:
                df = pd.read_csv(file, on_bad_lines='skip')

                # Corrigido com os nomes de coluna corretos do seu log
                ids = [str(item) for item in df["id"].tolist()]
                documents = df["Nome"].tolist() # <-- CORREÇÃO APLICADA AQUI

                collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=[{"source": file}] * len(ids)
                )

            except KeyError as e:
                print(f"ERRO: A coluna {e} não foi encontrada no arquivo {file}. Verifique os nomes das colunas e corrija o código.")
                return None
            except Exception as e:
                print(f"Ocorreu um erro inesperado ao processar {file}: {e}")
                return None

        print("Dados carregados com sucesso!")
    else:
        print("Collection already exists and contains data.")

    return collection