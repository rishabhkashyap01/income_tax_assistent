import streamlit as st
import time
import os
from src.rag_engine import get_rag_chain

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="India Tax E-Filing Assistant",
    page_icon="🇮🇳",
    layout="wide"
)

# --- 2. STYLING (Government Portal Theme) ---
st.markdown("""
    <style>
    /* 1. Ensure the app background is light */
    .stApp { background-color: #fcfcfc; }
    
    /* 2. Target the actual text content inside chat bubbles */
    .stChatMessage p, .stChatMessage div { 
        color: #1a1a1a !important; 
    }
    
    /* 3. Style the headers */
    .main-header { 
        color: #1e3a8a !important; 
        font-size: 2.5rem; 
        font-weight: 700; 
        text-align: center; 
    }

    /* 4. Optional: Make the chat bubbles slightly darker for contrast */
    [data-testid="stChatMessage"] {
        background-color: #f0f2f6 !important;
        border: 1px solid #e5e7eb;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. INITIALIZE ENGINE (Cached for speed) ---
@st.cache_resource
def init_rag():
    try:
        return get_rag_chain()
    except Exception as e:
        st.error(f"Error loading RAG Engine: {e}")
        return None

rag_chain = init_rag()

# --- 4. SIDEBAR (Information & Stats) ---
with st.sidebar:
    st.image("asset/income-tax-icon.jpeg", width=120)
    st.title("Tax-Bot Admin")
    st.markdown("---")
    
    # Check if DB exists
    if os.path.exists("data/chroma_db"):
        st.success("✅ Knowledge Base Connected")
        # Count files in your rules folder
        rule_count = len(os.listdir("data/raw_markdown/rules")) if os.path.exists("data/raw_markdown/rules") else 0
        st.metric("Rules Vectorized", f"{rule_count}")
    else:
        st.warning("⚠️ Knowledge Base not found. Run ingest.py!")

    if st.button("Clear Conversation"):
        st.session_state.messages = []
        st.rerun()

# --- 5. MAIN UI ---
st.markdown("<h1 class='main-header'>🇮🇳 Income Tax AI Assistant</h1>", unsafe_allow_html=True)
st.info("Ask me anything about Income Tax Rules (1962). I can explain specific Rules or help with filing logic.")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Input Logic
if prompt := st.chat_input("Ex: What are the conditions under Rule 2D?"):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate Response
    with st.chat_message("assistant"):
        if rag_chain is None:
            st.error("RAG Engine not initialized. Please check your setup.")
        else: 
            with st.spinner("Analyzing Tax Acts & Rules..."):
                # Call the modern LCEL chain from rag_engine.py
                # This returns the generated string from your LLM (Groq)
                response = rag_chain.invoke({"input": prompt})

            message_placeholder = st.empty()
            full_response = ""
                
            # Typing effect
            for chunk in response.split(" "):
                full_response += chunk + " "
                time.sleep(0.04)
                message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

# --- 6. DISCLAIMER ---
st.markdown("---")
st.caption("**Disclaimer:** This is an AI research project. All information provided should be verified with the official Income Tax portal or a certified Tax Practitioner.")