import os
import pandas as pd
import chromadb
from PyPDF2 import PdfReader
from chromadb.utils.embedding_functions import GoogleGenerativeAiEmbeddingFunction
from langchain.text_splitter import CharacterTextSplitter
from dotenv import load_dotenv
import re

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHROMA_PATH = "chroma_db"


def clean_text(text: str):
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)  # junta espaços quebrados
    text = text.replace("\x00", "")  # remove caracteres invisíveis
    return text.strip()


def read_pdf_pages(file_path):
    pdf = PdfReader(file_path)
    pages_text = []
    for page_num, page in enumerate(pdf.pages):
        try:
            page_text = clean_text(page.extract_text())
            if page_text:
                pages_text.append((page_num, page_text))
        except:
            continue
    return pages_text


def read_xlsx(file_path):
    df = pd.read_excel(file_path).fillna("")

    rows = []
    for _, row in df.iterrows():
        row_text = " | ".join([str(v) for v in row.values])
        if len(row_text.strip()) > 5:
            rows.append(row_text)

    return clean_text("\n".join(rows))


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
        print("Iniciando ingestão de documentos...")

        text_splitter = CharacterTextSplitter(
            separator="\n",
            chunk_size=900,
            chunk_overlap=150
        )

        for file in doc_files:
            ext = os.path.splitext(file)[1].lower()

            try:
                if ext == ".pdf":
                    print(f"Processando PDF: {file}")
                    pages = read_pdf_pages(file)

                    for page_num, page_text in pages:
                        chunks = text_splitter.split_text(page_text)

                        for i, chunk in enumerate(chunks):
                            collection.add(
                                ids=[f"{os.path.basename(file)}_p{page_num}_c{i}"],
                                documents=[chunk],
                                metadatas=[{
                                    "source": file,
                                    "page": page_num,
                                    "type": "pdf"
                                }]
                            )

                elif ext == ".xlsx":
                    print(f"Processando Excel: {file}")
                    text = read_xlsx(file)
                    chunks = text_splitter.split_text(text)

                    for i, chunk in enumerate(chunks):
                        collection.add(
                            ids=[f"{os.path.basename(file)}_c{i}"],
                            documents=[chunk],
                            metadatas=[{
                                "source": file,
                                "type": "excel"
                            }]
                        )

                else:
                    print(f"Ignorado: {file}")
                    continue

            except Exception as e:
                print(f"Erro em {file}: {e}")
                continue

        print("Documentos carregados com sucesso!")

    else:
        print(f"Collection já existente com {collection.count()} chunks")

    return collection
