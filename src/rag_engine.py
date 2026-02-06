import os
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from operator import itemgetter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

DB_DIR = "data/chroma_db"
GROQ_MODEL = "llama-3.3-70b-versatile" 

def get_rag_chain():
    # Ensure API Key is present
    api_key = os.getenv("GROQ_API_KEY")
    
    if not api_key:
        raise ValueError("GROQ_API_KEY not found. Check your .env file!")

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    if not os.path.exists(DB_DIR):
        raise FileNotFoundError(f"Vector DB not found at {DB_DIR}. Run ingest.py first!")
        
    vector_db = Chroma(
        persist_directory=DB_DIR, 
        embedding_function=embeddings
    )
    
    # IMPROVEMENT: Use 'mmr' search to get diverse context from that 916-page PDF
    retriever = vector_db.as_retriever(search_type="mmr", search_kwargs={"k": 5})

    llm = ChatGroq(model=GROQ_MODEL, temperature=0, groq_api_key=api_key)

    # UPDATED: Changed {question} to {input} for compatibility
    template = """
    You are an expert Indian Tax Assistant. Use the following retrieved context 
    from the Income Tax Act and Rules to answer the user's question.
    
    Context: {context}
    
    Question: {input}
    
    Answer instructions:
    - If the answer isn't in the context, say "I don't have that specific data in my current tax records."
    - Always cite the Section number or Rule number from the context.
    - Be concise and use bullet points for tax slabs.
    
    Helpful Answer:"""
    
    prompt = ChatPromptTemplate.from_template(template)

    def format_docs(docs):
        # We also want to extract page numbers if available in metadata
        formatted = []
        for doc in docs:
            page_info = f"[Source: {doc.metadata.get('source', 'Tax Act')} - Page {doc.metadata.get('page', 'N/A')}]"
            formatted.append(f"{page_info}\n{doc.page_content}")
        return "\n\n---\n\n".join(formatted)

    # The Chain
    rag_chain = (
    {
        "context": itemgetter("input") | retriever | format_docs, 
        "input": itemgetter("input")
    }
    | prompt
    | llm
    | StrOutputParser()
)

    return rag_chain