import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

def ingest_large_tax_act():
    PDF_PATH = "data/raw_pdf/income_tax_act_1961.pdf"
    DB_PATH = "data/chroma_db"

    # 1. LOAD: Optimized for large files
    print("📖 Loading 916-page Tax Act... this may take a minute.")
    loader = PyPDFLoader(PDF_PATH)
    # This loads pages one by one to save memory
    pages = loader.load()
    print(f"✅ Successfully loaded {len(pages)} pages.")

    # 2. SPLIT: Strategic splitting for legal text
    # We use a larger chunk size (1500) because legal sentences are long.
    # We use 'separators' to prioritize splitting at Sections or Chapters.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=300,
        separators=["\nSection ", "\nCHAPTER ", "\n\n", "\n", " "]
    )
    
    chunks = text_splitter.split_documents(pages)
    print(f"✂️ Created {len(chunks)} semantic chunks.")

    # 3. EMBED: Local CPU execution
    print("💡 Generating embeddings (all-MiniLM-L6-v2)...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # 4. STORE: Persistent ChromaDB
    # We add 'allow_oversize_upload' logic if needed, but Chroma handles this well.
    vector_db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=DB_PATH
    )
    
    print(f"🚀 Success! Database updated at {DB_PATH}")

if __name__ == "__main__":
    ingest_large_tax_act()