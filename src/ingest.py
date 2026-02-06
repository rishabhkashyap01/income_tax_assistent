import os
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# 1. Configuration
DATA_PATH = "data/raw_markdown/" # Folder where your scraped data lives
DB_PATH = "data/chroma_db"

def run_ingestion():
    # 2. LOAD: Support both PDF and Markdown files
    print("--- Loading documents from data folder ---")
    
    # Loader for Markdown (scraped web data)
    md_loader = DirectoryLoader(
        DATA_PATH, 
        glob="**/*.md", 
        loader_cls=UnstructuredMarkdownLoader
    )
    
    # Loader for PDFs (official tax forms/publications)
    pdf_loader = DirectoryLoader(
        DATA_PATH, 
        glob="**/*.pdf", 
        loader_cls=PyPDFLoader
    )

    docs = md_loader.load() + pdf_loader.load()
    print(f"Loaded {len(docs)} documents.")

    # 3. SPLIT: Use a larger chunk size for tax laws to keep context intact
    # Tax sections are often 500-1000 characters long.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200, 
        chunk_overlap=200,
        separators=["\n### ", "\n## ", "\n# ", "\n\n", "\n", " "]
    )
    chunks = text_splitter.split_documents(docs)
    print(f"Created {len(chunks)} chunks.")

    # 4. EMBED: Use the same FREE local model as rag_engine.py
    print("--- Creating embeddings (Local CPU) ---")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # 5. STORE: Save to the persistent Chroma directory
    vector_db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=DB_PATH
    )
    
    print(f"Success! Database created at {DB_PATH}")

if __name__ == "__main__":
    run_ingestion()