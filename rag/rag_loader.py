import os
import pandas as pd
import chromadb
from PyPDF2 import PdfReader
from chromadb.utils.embedding_functions import GoogleGenerativeAiEmbeddingFunction
from langchain_text_splitters import CharacterTextSplitter
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHROMA_PATH = "chroma_db"


# Função que lê PDFs página a página
def read_pdf_pages(file_path):
    pdf = PdfReader(file_path)
    pages_text = []
    for page_num, page in enumerate(pdf.pages):
        page_text = page.extract_text()
        if page_text:
            pages_text.append((page_num, page_text))
    return pages_text


# Função que lê Excel
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

        # Divisão mais segura (≈ 1000 caracteres por chunk)
        text_splitter = CharacterTextSplitter(
            separator="\n",
            chunk_size=1000,
            chunk_overlap=100
        )

        for file in doc_files:
            try:
                ext = os.path.splitext(file)[1].lower()

                # Caso PDF → dividir página por página
                if ext == ".pdf":
                    print(f"Processando PDF por páginas: {file}")
                    pages = read_pdf_pages(file)

                    for page_num, page_text in pages:
                        chunks = text_splitter.split_text(page_text)
                        ids = [
                            f"{os.path.basename(file)}_p{page_num}_chunk{i}"
                            for i in range(len(chunks))
                        ]

                        collection.add(
                            ids=ids,
                            documents=chunks,
                            metadatas=[{"source": f"{file}_p{page_num}"}] * len(chunks)
                        )

                # Caso Excel → texto inteiro dividido em chunks
                elif ext in [".xlsx"]:
                    print(f"Processando Excel: {file}")
                    text = read_xlsx(file)
                    chunks = text_splitter.split_text(text)
                    ids = [
                        f"{os.path.basename(file)}_chunk{i}" for i in range(len(chunks))
                    ]

                    collection.add(
                        ids=ids,
                        documents=chunks,
                        metadatas=[{"source": file}] * len(chunks)
                    )

                else:
                    print(f"Ignorando arquivo {file} (tipo não suportado)")
                    continue

            except Exception as e:
                print(f"Erro ao processar {file}: {e}")
                continue

        print("Documentos carregados com sucesso!")

    else:
        print("Collection já existe com dados.")

    return collection
