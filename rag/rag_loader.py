import os
import pandas as pd
import chromadb
from PyPDF2 import PdfReader
from chromadb.utils.embedding_functions import GoogleGenerativeAiEmbeddingFunction
from langchain.text_splitter import CharacterTextSplitter
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHROMA_PATH = "chroma_db"

def read_pdf(file_path):
    pdf = PdfReader(file_path)
    text = ""
    for page in pdf.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text

def read_xlsx(file_path):
    df = pd.read_excel(file_path)
    text = ""
    for _, row in df.iterrows():
        text += " | ".join([str(v) for v in row.values]) + "\n"
    return text

def load_documents_to_chroma(doc_files, collection_name="nutrientes_collection"):
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    embedding_fn = GoogleGenerativeAiEmbeddingFunction(
        api_key=GEMINI_API_KEY, 
        model_name="models/text-embedding-004"
    )

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_fn
    )

    if collection.count() == 0:
        print("Collection vazia. Carregando documentos...")

        text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)

        for file in doc_files:
            try:
                ext = os.path.splitext(file)[1].lower()
                if ext == ".pdf":
                    text = read_pdf(file)
                elif ext in [".xlsx"]:
                    text = read_xlsx(file)
                else:
                    print(f"Ignorando arquivo {file} (tipo não suportado)")
                    continue

                chunks = text_splitter.split_text(text)
                ids = [f"{os.path.basename(file)}_{i}" for i in range(len(chunks))]

                collection.add(
                    ids=ids,
                    documents=chunks,
                    metadatas=[{"source": file}] * len(chunks)
                )

            except Exception as e:
                print(f"Erro ao processar {file}: {e}")
                continue

        print("Documentos carregados com sucesso!")
    else:
        print("Collection já existe com dados.")

    return collection
