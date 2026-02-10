import os
import re
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from operator import itemgetter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

DB_DIR = "data/chroma_db"
GROQ_MODEL = "llama-3.3-70b-versatile"


def _extract_rule_numbers(query: str) -> list[str]:
    """Extract rule numbers mentioned in the user query.

    Handles patterns like:
      - "Rule 3A", "rule 3A", "Rule 11-OB"
      - "Rules 2BA and 3C"
      - "rule no. 114E"
    """
    pattern = r"[Rr]ules?\s*(?:[Nn]o\.?\s*)?(\d+[A-Za-z]*(?:-[A-Za-z0-9]+)?)"
    matches = re.findall(pattern, query)
    return [m.upper() for m in matches]


def _extract_section_numbers(query: str) -> list[str]:
    """Extract section numbers mentioned in the user query.

    Handles patterns like:
      - "Section 80C", "section 10(14)"
      - "Sec. 139"
    """
    pattern = r"[Ss]ec(?:tion|\.)\s*(\d+[A-Z]*)"
    return re.findall(pattern, query)


def get_rag_chain():
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

    # Semantic retriever for general questions
    semantic_retriever = vector_db.as_retriever(
        search_type="mmr", search_kwargs={"k": 5}
    )

    def hybrid_retrieve(query: str):
        """Smart retriever: exact metadata match for rule/section numbers + semantic search."""
        targeted_docs = []
        seen_ids = set()

        # 1. If the query mentions specific rule numbers, fetch those directly
        rule_nums = _extract_rule_numbers(query)
        for rn in rule_nums:
            try:
                results = vector_db.similarity_search(
                    query,
                    k=4,
                    filter={"rule_number": rn},
                )
                for doc in results:
                    doc_id = doc.page_content[:100]
                    if doc_id not in seen_ids:
                        targeted_docs.append(doc)
                        seen_ids.add(doc_id)
            except Exception:
                pass

        # 2. Semantic search for broader context
        semantic_docs = semantic_retriever.invoke(query)
        for doc in semantic_docs:
            doc_id = doc.page_content[:100]
            if doc_id not in seen_ids:
                targeted_docs.append(doc)
                seen_ids.add(doc_id)

        # Targeted (exact rule) docs come first, then semantic results
        return targeted_docs[:8]

    llm = ChatGroq(model=GROQ_MODEL, temperature=0, groq_api_key=api_key)

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
        formatted = []
        for doc in docs:
            source = doc.metadata.get('source', 'Tax Act')
            page = doc.metadata.get('page', 'N/A')
            rule = doc.metadata.get('rule_number', '')
            if rule:
                page_info = f"[Source: {source} | Rule {rule}]"
            else:
                page_info = f"[Source: {source} - Page {page}]"
            formatted.append(f"{page_info}\n{doc.page_content}")
        return "\n\n---\n\n".join(formatted)

    rag_chain = (
        {
            "context": itemgetter("input") | RunnableLambda(hybrid_retrieve) | format_docs,
            "input": itemgetter("input")
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return rag_chain