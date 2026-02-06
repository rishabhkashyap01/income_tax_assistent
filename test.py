from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader

DATA_PATH = "data/raw_markdown/" # Renamed for clarity

# Added show_progress for better UX
pdf_loader = DirectoryLoader(
    DATA_PATH, 
    glob="**/*.pdf", 
    loader_cls=PyPDFLoader,
    show_progress=True 
)

docs = pdf_loader.load()

# Check if any documents were actually found
if not docs:
    print("Warning: No documents found in the specified path.")
else:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200, 
        chunk_overlap=200,
        # Added \n\n earlier in case Markdown headers aren't present in the PDF text
        separators=["\n\n", "\n", " ", ""] 
    )
    chunks = text_splitter.split_documents(docs)

# Print details for the first 3 chunks as a sample
for i, chunk in enumerate(chunks[:3]):
    print(f"--- Chunk {i+1} ---")
    print(f"Source: {chunk.metadata['source']}")
    print(f"Page: {chunk.metadata.get('page', 'N/A')}")
    print(f"Content Preview: {chunk.page_content[:200]}...") # First 200 characters
    print("\n")