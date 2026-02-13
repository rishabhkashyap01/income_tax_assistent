import streamlit as st
import time
import os
from src.rag_engine import get_rag_chain
from src.itr_models import ITRFiling
from src.itr_prompts import FILING_STEPS, STEP_LABELS
from src.filing_engine import process_filing_message, is_tax_question
from src.filing_storage import save_filing, update_filing, load_filing, list_filings, delete_filing
from src.auth import authenticate_user, register_user, create_session, validate_session, delete_session

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="TaxAssist - Smart ITR Filing",
    page_icon="https://api.iconify.design/mdi/file-document-check.svg?color=%23a855f7",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- 2. DARK THEME CSS ---
# All colors are hardcoded (no CSS variables) for cross-browser compatibility
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ===== GLOBAL ===== */
.stApp {
    background: #0a0a0f !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: #e2e8f0 !important;
}

#MainMenu, footer, .stDeployButton { display: none !important; }
header[data-testid="stHeader"] { background: #0a0a0f !important; }

/* Sidebar toggle button — always white */
[data-testid="stSidebarCollapsedControl"] svg,
[data-testid="stSidebarCollapseButton"] svg,
[data-testid="collapsedControl"] svg {
    color: #ffffff !important;
    fill: #ffffff !important;
    stroke: #ffffff !important;
}
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarCollapsedControl"] button,
[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"],
[data-testid="collapsedControl"] button {
    color: #ffffff !important;
    opacity: 1 !important;
}

/* Force all text to be visible */
.stApp p, .stApp div, .stApp span, .stApp li, .stApp label,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
    color: #e2e8f0 !important;
}
.stMarkdown p, .stMarkdown li, .stMarkdown span { color: #e2e8f0 !important; }

/* ===== SIDEBAR ===== */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d0d14 0%, #12121c 50%, #0d0d14 100%) !important;
    border-right: 1px solid rgba(139, 92, 246, 0.1) !important;
}
section[data-testid="stSidebar"] * { color: #c4b5fd !important; }
section[data-testid="stSidebar"] .stRadio label span { color: #a78bfa !important; font-weight: 500 !important; }
section[data-testid="stSidebar"] .stRadio label { transition: all 0.2s ease !important; }
section[data-testid="stSidebar"] hr { border-color: rgba(139, 92, 246, 0.15) !important; }

/* All buttons — unified purple gradient (matches Start New Filing) */
.stButton button {
    background: linear-gradient(135deg, #7c3aed, #a855f7, #7c3aed) !important;
    background-size: 200% 200% !important;
    border: none !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 20px rgba(124, 58, 237, 0.3) !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    backdrop-filter: blur(10px) !important;
}
.stButton button:hover {
    box-shadow: 0 8px 30px rgba(124, 58, 237, 0.5) !important;
    transform: translateY(-2px) !important;
}
.stButton button p {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

/* ===== HERO ===== */
.hero { text-align: center; padding: 1.5rem 0 1rem; }
.hero-title {
    font-size: 2.2rem; font-weight: 800;
    background: linear-gradient(135deg, #a855f7, #6366f1, #a855f7);
    background-size: 200% auto;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    margin-bottom: 0.25rem; letter-spacing: -0.03em;
    animation: shimmer 3s linear infinite;
}
@keyframes shimmer {
    to { background-position: 200% center; }
}
.hero-subtitle { font-size: 0.95rem; color: #64748b !important; font-weight: 400; }

/* ===== INFO BANNER ===== */
.info-banner {
    background: rgba(139, 92, 246, 0.06);
    border: 1px solid rgba(139, 92, 246, 0.15);
    border-radius: 14px;
    padding: 0.85rem 1.25rem;
    font-size: 0.88rem;
    color: #a78bfa !important;
    margin-bottom: 1rem;
    display: flex; align-items: center; gap: 0.5rem;
    backdrop-filter: blur(10px);
}
.info-banner .icon { font-size: 1.1rem; }
.info-banner strong { color: #c4b5fd !important; }

/* ===== CHAT MESSAGES ===== */
[data-testid="stChatMessage"] {
    background: rgba(255, 255, 255, 0.03) !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    border-radius: 16px !important;
    padding: 1rem 1.25rem !important;
    margin-bottom: 0.75rem !important;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2) !important;
    backdrop-filter: blur(10px) !important;
    transition: all 0.3s ease !important;
}
[data-testid="stChatMessage"]:hover {
    border-color: rgba(139, 92, 246, 0.15) !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3) !important;
}
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] div,
[data-testid="stChatMessage"] li,
[data-testid="stChatMessage"] span,
[data-testid="stChatMessage"] strong,
[data-testid="stChatMessage"] code {
    color: #e2e8f0 !important;
    font-size: 0.92rem !important;
    line-height: 1.7 !important;
}
[data-testid="stChatMessage"] strong { color: #c4b5fd !important; }

/* ===== CHAT INPUT ===== */
[data-testid="stChatInput"],
[data-testid="stChatInput"] > div,
[data-testid="stChatInput"] [data-baseweb] {
    border-radius: 16px !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    background: #1a1a2e !important;
    background-color: #1a1a2e !important;
    transition: all 0.3s ease !important;
}
[data-testid="stChatInput"]:focus-within,
[data-testid="stChatInput"]:focus-within > div,
[data-testid="stChatInput"]:focus-within [data-baseweb] {
    border-color: rgba(139, 92, 246, 0.4) !important;
    box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.1), 0 4px 20px rgba(139, 92, 246, 0.1) !important;
    background: #1e1e35 !important;
    background-color: #1e1e35 !important;
}
[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] input,
[data-testid="stChatInput"] [data-baseweb] textarea {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    caret-color: #a855f7 !important;
    font-size: 0.95rem !important;
    background: #1a1a2e !important;
    background-color: #1a1a2e !important;
}
[data-testid="stChatInput"] textarea:focus,
[data-testid="stChatInput"] [data-baseweb] textarea:focus {
    background: #1e1e35 !important;
    background-color: #1e1e35 !important;
}
[data-testid="stChatInput"] textarea::placeholder,
[data-testid="stChatInput"] input::placeholder {
    color: #64748b !important;
    -webkit-text-fill-color: #64748b !important;
}

/* ===== PROGRESS BAR ===== */
.stProgress > div > div {
    background: linear-gradient(90deg, #7c3aed, #a855f7, #6366f1) !important;
    border-radius: 100px !important;
    box-shadow: 0 0 15px rgba(139, 92, 246, 0.3) !important;
}
.stProgress > div { background: rgba(255, 255, 255, 0.05) !important; border-radius: 100px !important; }

/* ===== STEP TRACKER ===== */
.step-item {
    display: flex; align-items: center; gap: 0.65rem;
    padding: 0.45rem 0.75rem; margin: 0.15rem 0;
    border-radius: 10px; font-size: 0.82rem;
    transition: all 0.2s ease;
}
.step-item.completed { color: #34d399 !important; }
.step-item.current {
    background: rgba(139, 92, 246, 0.12);
    border: 1px solid rgba(139, 92, 246, 0.2);
    color: #c4b5fd !important; font-weight: 600;
    box-shadow: 0 2px 10px rgba(139, 92, 246, 0.1);
}
.step-item.pending { color: rgba(255, 255, 255, 0.2) !important; }

/* ===== FEATURE CARDS ===== */
.start-card {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 20px;
    padding: 2rem 1.5rem; text-align: center;
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    cursor: pointer;
    backdrop-filter: blur(10px);
    position: relative;
    overflow: hidden;
}
.start-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(139, 92, 246, 0.3), transparent);
    opacity: 0;
    transition: opacity 0.4s ease;
}
.start-card:hover {
    border-color: rgba(139, 92, 246, 0.2);
    box-shadow: 0 8px 40px rgba(139, 92, 246, 0.08), 0 0 0 1px rgba(139, 92, 246, 0.1);
    transform: translateY(-4px);
}
.start-card:hover::before { opacity: 1; }
.start-card .card-icon { font-size: 2.5rem; margin-bottom: 0.75rem; }
.start-card .card-title { font-size: 1.1rem; font-weight: 600; color: #e2e8f0 !important; margin-bottom: 0.25rem; }
.start-card .card-desc { font-size: 0.85rem; color: #64748b !important; }

/* ===== STATUS BADGE ===== */
.status-badge {
    display: inline-flex; align-items: center; gap: 0.4rem;
    padding: 0.35rem 0.85rem; border-radius: 100px;
    font-size: 0.78rem; font-weight: 500;
}
.status-badge.connected {
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.2);
    color: #34d399 !important;
}

/* ===== STAT CARD ===== */
.stat-card {
    background: rgba(139, 92, 246, 0.05);
    border: 1px solid rgba(139, 92, 246, 0.12);
    border-radius: 14px; padding: 0.85rem 1rem; margin-top: 0.75rem;
}
.stat-label {
    font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: 0.08em; color: rgba(255, 255, 255, 0.35) !important;
    margin-bottom: 0.2rem;
}
.stat-value { font-size: 1.5rem; font-weight: 700; color: #c4b5fd !important; }

/* ===== DISCLAIMER ===== */
.disclaimer {
    text-align: center; padding: 1rem 0 0.5rem;
    font-size: 0.75rem; color: #475569 !important;
    border-top: 1px solid rgba(255, 255, 255, 0.04); margin-top: 1.5rem;
}
.disclaimer a { color: #a78bfa !important; text-decoration: none; }
.disclaimer a:hover { color: #c4b5fd !important; }

/* ===== LOGIN PAGE ===== */
.login-wrapper {
    display: flex; justify-content: center; align-items: center;
    min-height: 70vh; padding: 2rem 0;
}
.login-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 24px;
    padding: 2.5rem 2rem;
    backdrop-filter: blur(20px);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
    position: relative;
    overflow: hidden;
}
.login-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, #a855f7, #6366f1, transparent);
}
.login-brand {
    text-align: center; margin-bottom: 2rem;
}
.login-brand-icon {
    width: 60px; height: 60px;
    background: linear-gradient(135deg, #7c3aed, #a855f7);
    border-radius: 16px;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 1.75rem; margin-bottom: 1rem;
    box-shadow: 0 8px 25px rgba(124, 58, 237, 0.3);
}
.login-brand-title {
    font-size: 1.75rem; font-weight: 800; color: #f1f5f9 !important;
    letter-spacing: -0.03em; margin-bottom: 0.25rem;
}
.login-brand-sub {
    font-size: 0.85rem; color: #64748b !important;
}
/* ===== FORM INPUTS (dark theme — high contrast text) ===== */
.stTextInput input,
.stTextInput input[type="text"],
.stTextInput input[type="password"] {
    background: #1a1a2e !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    border-radius: 12px !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    padding: 0.65rem 0.85rem !important;
    transition: all 0.3s ease !important;
    font-size: 0.95rem !important;
}
.stTextInput input:focus,
.stTextInput input[type="text"]:focus,
.stTextInput input[type="password"]:focus {
    border-color: rgba(139, 92, 246, 0.5) !important;
    box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.1) !important;
    background: #1e1e35 !important;
}
.stTextInput input::placeholder { color: #64748b !important; -webkit-text-fill-color: #64748b !important; }
.stTextInput label { color: #94a3b8 !important; font-weight: 500 !important; font-size: 0.85rem !important; }

/* Form submit buttons */
.stFormSubmitButton button {
    background: linear-gradient(135deg, #7c3aed, #a855f7) !important;
    border: none !important;
    color: #ffffff !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    padding: 0.65rem 1.5rem !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    box-shadow: 0 4px 20px rgba(124, 58, 237, 0.25) !important;
}
.stFormSubmitButton button:hover {
    box-shadow: 0 8px 30px rgba(124, 58, 237, 0.4) !important;
    transform: translateY(-2px) !important;
}

/* ===== TABS (login/register) ===== */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255, 255, 255, 0.03) !important;
    border-radius: 14px !important;
    padding: 4px !important;
    gap: 4px !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 10px !important;
    color: #64748b !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(139, 92, 246, 0.15) !important;
    color: #c4b5fd !important;
}
.stTabs [data-baseweb="tab-highlight"] { background: transparent !important; }
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* ===== DELETE BUTTONS (marker-based: collapse wrapper + adjacent sibling) ===== */
.delete-marker { display: none; }
/* Collapse the entire Streamlit element container wrapping the marker */
div:has(> [data-testid="stMarkdown"] .delete-marker) {
    display: none !important;
}
/* Style the delete button (next sibling after collapsed marker wrapper) */
div:has(> [data-testid="stMarkdown"] .delete-marker) + div button {
    background: rgba(239, 68, 68, 0.1) !important;
    border: 1px solid rgba(239, 68, 68, 0.3) !important;
    color: #ef4444 !important;
    -webkit-text-fill-color: #ef4444 !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    transition: all 0.3s ease !important;
}
div:has(> [data-testid="stMarkdown"] .delete-marker) + div button:hover {
    background: rgba(239, 68, 68, 0.25) !important;
    border-color: #ef4444 !important;
    box-shadow: 0 4px 15px rgba(239, 68, 68, 0.2) !important;
    transform: translateY(-1px) !important;
}
div:has(> [data-testid="stMarkdown"] .delete-marker) + div button p {
    color: #ef4444 !important;
    -webkit-text-fill-color: #ef4444 !important;
}

/* ===== ALERTS ===== */
.stAlert { border-radius: 12px !important; }

/* ===== SPINNER ===== */
.stSpinner > div { border-top-color: #a855f7 !important; }

/* ===== TOAST ===== */
[data-testid="stToast"] { background: #1a1a2e !important; border: 1px solid rgba(139, 92, 246, 0.2) !important; }

/* ===== SCROLLBAR ===== */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(139, 92, 246, 0.2); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(139, 92, 246, 0.4); }

/* ===== LOADING SCREEN ===== */
.loading-screen {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: #0a0a0f;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    z-index: 999999;
}
.loading-logo {
    width: 72px; height: 72px;
    background: linear-gradient(135deg, #7c3aed, #a855f7);
    border-radius: 18px;
    display: flex; align-items: center; justify-content: center;
    margin-bottom: 1.5rem;
    box-shadow: 0 8px 30px rgba(124, 58, 237, 0.4);
    animation: logo-pulse 2s ease-in-out infinite;
}
@keyframes logo-pulse {
    0%, 100% { box-shadow: 0 8px 30px rgba(124, 58, 237, 0.4); transform: scale(1); }
    50% { box-shadow: 0 16px 60px rgba(124, 58, 237, 0.6); transform: scale(1.08); }
}
.loading-title {
    font-size: 1.6rem; font-weight: 800; color: #f1f5f9;
    letter-spacing: -0.03em; margin-bottom: 0.35rem;
}
.loading-subtitle {
    font-size: 0.85rem; color: #64748b; margin-bottom: 2rem;
}
.loading-bar {
    width: 220px; height: 3px;
    background: rgba(255, 255, 255, 0.06);
    border-radius: 3px; overflow: hidden;
}
.loading-bar-fill {
    width: 40%; height: 100%;
    background: linear-gradient(90deg, #7c3aed, #a855f7, #6366f1);
    border-radius: 3px;
    animation: bar-slide 1.5s ease-in-out infinite;
}
@keyframes bar-slide {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(350%); }
}
.loading-dots {
    margin-top: 1.25rem;
    font-size: 0.8rem; color: #475569;
    letter-spacing: 0.05em;
}
.loading-dots span {
    animation: dot-fade 1.4s ease-in-out infinite;
}
.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot-fade {
    0%, 80%, 100% { opacity: 0.2; }
    40% { opacity: 1; }
}

/* ===== GLOW EFFECT (background) ===== */
.glow-bg {
    position: fixed;
    top: -30%; left: -10%;
    width: 500px; height: 500px;
    background: radial-gradient(circle, rgba(124, 58, 237, 0.06) 0%, transparent 70%);
    pointer-events: none;
    z-index: 0;
}
.glow-bg-2 {
    position: fixed;
    bottom: -20%; right: -10%;
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(99, 102, 241, 0.04) 0%, transparent 70%);
    pointer-events: none;
    z-index: 0;
}
</style>

<div class="glow-bg"></div>
<div class="glow-bg-2"></div>
""", unsafe_allow_html=True)


# --- 3. INITIALIZE RAG ENGINE (Cached, with loading screen) ---
@st.cache_resource(show_spinner=False)
def init_rag():
    try:
        return get_rag_chain()
    except Exception as e:
        return None

_loading = st.empty()
_loading.markdown("""
<div class="loading-screen">
    <div class="loading-logo">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M14 2H6C4.9 2 4 2.9 4 4V20C4 21.1 4.9 22 6 22H18C19.1 22 20 21.1 20 20V8L14 2Z" fill="rgba(255,255,255,0.15)" stroke="white" stroke-width="1.5"/>
            <path d="M14 2V8H20" stroke="white" stroke-width="1.5"/>
            <path d="M9 15L11 17L15 13" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    </div>
    <div class="loading-title">TaxAssist</div>
    <div class="loading-subtitle">Initializing AI Engine</div>
    <div class="loading-bar"><div class="loading-bar-fill"></div></div>
    <div class="loading-dots">
        Loading knowledge base<span>.</span><span>.</span><span>.</span>
    </div>
</div>
""", unsafe_allow_html=True)

rag_chain = init_rag()
_loading.empty()

# --- 4. SESSION STATE INIT ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = None
if "mode" not in st.session_state:
    st.session_state.mode = "qa"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "filing" not in st.session_state:
    st.session_state.filing = None
if "filing_messages" not in st.session_state:
    st.session_state.filing_messages = []
if "filing_id" not in st.session_state:
    st.session_state.filing_id = None


# --- 4b. RESTORE SESSION FROM QUERY PARAMS ---
if not st.session_state.authenticated:
    session_token = st.query_params.get("session")
    if session_token:
        user = validate_session(session_token)
        if user:
            st.session_state.authenticated = True
            st.session_state.user_id = str(user["_id"])
            st.session_state.username = user["username"]


# --- 5. AUTH GATE ---
def show_login_page():
    """Render login/register UI with modern dark design."""

    st.markdown("""
    <div class="login-wrapper">
        <div style="width: 100%; max-width: 440px;">
            <div class="login-brand">
                <div class="login-brand-icon">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M14 2H6C4.9 2 4 2.9 4 4V20C4 21.1 4.9 22 6 22H18C19.1 22 20 21.1 20 20V8L14 2Z" fill="rgba(255,255,255,0.15)" stroke="white" stroke-width="1.5"/>
                        <path d="M14 2V8H20" stroke="white" stroke-width="1.5"/>
                        <path d="M9 15L11 17L15 13" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </div>
                <div class="login-brand-title">TaxAssist</div>
                <div class="login-brand-sub">AI-Powered Income Tax Filing Assistant</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_left, col_center, col_right = st.columns([1.2, 2, 1.2])
    with col_center:
        tab_login, tab_register = st.tabs(["Sign In", "Create Account"])

        with tab_login:
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="Enter your username")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                st.markdown("<br>", unsafe_allow_html=True)
                submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)
                if submitted:
                    if not username or not password:
                        st.error("Please fill in both fields.")
                    else:
                        user = authenticate_user(username, password)
                        if user:
                            st.session_state.authenticated = True
                            st.session_state.user_id = str(user["_id"])
                            st.session_state.username = user["username"]
                            token = create_session(str(user["_id"]))
                            st.query_params["session"] = token
                            st.rerun()
                        else:
                            st.error("Invalid username or password.")

        with tab_register:
            with st.form("register_form"):
                new_username = st.text_input("Choose a username", placeholder="Pick a username")
                new_password = st.text_input("Choose a password", type="password", placeholder="Min 6 characters")
                confirm_password = st.text_input("Confirm password", type="password", placeholder="Re-enter password")
                st.markdown("<br>", unsafe_allow_html=True)
                submitted = st.form_submit_button("Create Account", type="primary", use_container_width=True)
                if submitted:
                    if not new_username or not new_password:
                        st.error("Please fill in all fields.")
                    elif len(new_password) < 6:
                        st.error("Password must be at least 6 characters.")
                    elif new_password != confirm_password:
                        st.error("Passwords do not match.")
                    else:
                        user = register_user(new_username, new_password)
                        if user:
                            st.session_state.authenticated = True
                            st.session_state.user_id = str(user["_id"])
                            st.session_state.username = user["username"]
                            token = create_session(str(user["_id"]))
                            st.query_params["session"] = token
                            st.rerun()
                        else:
                            st.error("Username already taken. Try a different one.")

if not st.session_state.authenticated:
    show_login_page()
    st.stop()


# ================================================================
# Everything below only runs if authenticated
# ================================================================

# --- 6. SIDEBAR ---
with st.sidebar:
    # Logo & Brand
    st.markdown("""
    <div style="text-align:center; padding: 1.25rem 0 0.5rem;">
        <div style="
            width: 44px; height: 44px;
            background: linear-gradient(135deg, #7c3aed, #a855f7);
            border-radius: 12px;
            display: inline-flex; align-items: center; justify-content: center;
            margin-bottom: 0.5rem;
            box-shadow: 0 4px 15px rgba(124, 58, 237, 0.3);
        ">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M14 2H6C4.9 2 4 2.9 4 4V20C4 21.1 4.9 22 6 22H18C19.1 22 20 21.1 20 20V8L14 2Z" fill="rgba(255,255,255,0.2)" stroke="white" stroke-width="1.5"/>
                <path d="M14 2V8H20" stroke="white" stroke-width="1.5"/>
                <path d="M9 15L11 17L15 13" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        </div>
        <div style="font-size: 1.15rem; font-weight: 700; color: #f1f5f9 !important; letter-spacing: -0.01em;">TaxAssist</div>
        <div style="font-size: 0.7rem; color: rgba(196, 181, 253, 0.5) !important; letter-spacing: 0.08em; text-transform: uppercase;">Smart ITR Filing</div>
    </div>
    """, unsafe_allow_html=True)

    # User info + logout
    st.markdown(f"""
    <div style="text-align:center; font-size: 0.78rem; color: rgba(196, 181, 253, 0.5) !important; margin-bottom: 0.25rem;">
        Signed in as <strong style="color: #c4b5fd !important;">{st.session_state.username}</strong>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Logout", use_container_width=True):
        token = st.query_params.get("session")
        if token:
            delete_session(token)
        st.query_params.clear()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    st.markdown("---")

    # Mode selector
    mode = st.radio(
        "Mode",
        ["Q&A Assistant", "File ITR"],
        index=0 if st.session_state.mode == "qa" else 1,
        label_visibility="collapsed",
    )
    st.session_state.mode = "qa" if "Q&A" in mode else "filing"

    st.markdown("---")

    if st.session_state.mode == "qa":
        # -- Q&A sidebar --
        if os.path.exists("data/chroma_db"):
            st.markdown("""
            <div class="status-badge connected">
                <span style="font-size: 0.5rem;">&#9679;</span> Knowledge Base Active
            </div>
            """, unsafe_allow_html=True)

        else:
            st.warning("Knowledge Base not found")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    else:
        # -- Filing sidebar --
        filing = st.session_state.filing

        if filing is None:
            st.markdown("""
            <div style="text-align:center; padding: 1rem 0; color: rgba(196, 181, 253, 0.4) !important; font-size: 0.85rem;">
                Start a new filing or<br>resume a saved one
            </div>
            """, unsafe_allow_html=True)

            if st.button("Start New Filing", type="primary", use_container_width=True):
                st.session_state.filing = ITRFiling()
                st.session_state.filing_messages = []
                st.session_state.filing_id = None
                st.rerun()

            saved = list_filings(st.session_state.user_id)
            if saved:
                st.markdown("---")
                st.markdown("""
                <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; color: rgba(196, 181, 253, 0.3) !important; margin-bottom: 0.5rem;">
                    Saved Filings
                </div>
                """, unsafe_allow_html=True)
                for f in saved[:5]:
                    name = f['name'] or f['pan'] or 'Draft'
                    form = f['form_type'] or 'New'
                    label = f"{name} - {form}"
                    sb_col1, sb_col2 = st.columns([5, 1])
                    with sb_col1:
                        if st.button(label, key=f["filing_id"], use_container_width=True):
                            filing_obj, messages = load_filing(f["filing_id"])
                            st.session_state.filing = filing_obj
                            st.session_state.filing_messages = messages
                            st.session_state.filing_id = f["filing_id"]
                            st.rerun()
                    with sb_col2:
                        st.markdown('<span class="delete-marker"></span>', unsafe_allow_html=True)
                        if st.button("🗑", key=f"del_sb_{f['filing_id']}"):
                            delete_filing(f["filing_id"])
                            st.rerun()
        else:
            # Active filing -- progress tracker
            form_type = filing.form_type or "ITR-1"
            steps = FILING_STEPS.get(form_type, FILING_STEPS["ITR-1"])
            completed_count = len(filing.completed_steps)
            total = len(steps)

            st.markdown(f"""
            <div style="text-align:center; margin-bottom: 0.75rem;">
                <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; color: rgba(196, 181, 253, 0.3) !important;">Filing Progress</div>
                <div style="font-size: 1.75rem; font-weight: 800; color: #c4b5fd !important;">{completed_count}/{total}</div>
                <div style="font-size: 0.78rem; color: rgba(196, 181, 253, 0.4) !important;">{form_type or 'Determining...'}</div>
            </div>
            """, unsafe_allow_html=True)

            for step in steps:
                label = STEP_LABELS.get(step, step)
                if step in filing.completed_steps:
                    st.markdown(f'<div class="step-item completed"><span>&#10003;</span>{label}</div>', unsafe_allow_html=True)
                elif step == filing.current_step:
                    st.markdown(f'<div class="step-item current"><span>&#9654;</span>{label}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="step-item pending"><span>&#183;</span>{label}</div>', unsafe_allow_html=True)

            st.markdown("---")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Save", use_container_width=True):
                    if st.session_state.filing_id:
                        update_filing(filing, st.session_state.filing_id, st.session_state.filing_messages)
                    else:
                        fid = save_filing(filing, st.session_state.user_id, st.session_state.filing_messages)
                        st.session_state.filing_id = fid
                    st.toast("Progress saved!")

            with col2:
                if st.button("Exit", use_container_width=True):
                    if st.session_state.filing_id:
                        update_filing(filing, st.session_state.filing_id, st.session_state.filing_messages)
                    elif filing.personal.pan:
                        fid = save_filing(filing, st.session_state.user_id, st.session_state.filing_messages)
                        st.session_state.filing_id = fid
                    st.session_state.filing = None
                    st.session_state.filing_messages = []
                    st.session_state.filing_id = None
                    st.rerun()


# --- 7. MAIN CONTENT ---

st.markdown("""
<div class="hero">
    <div class="hero-title">TaxAssist Assistant</div>
    <div class="hero-subtitle">Your intelligent companion for Indian Income Tax</div>
</div>
""", unsafe_allow_html=True)


if st.session_state.mode == "qa":
    # ===================== Q&A MODE =====================
    st.markdown("""
    <div class="info-banner">
        <span class="icon">&#9889;</span>
        Ask anything about Income Tax Act 1961, Rules 1962, sections, deductions, or filing procedures.
    </div>
    """, unsafe_allow_html=True)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask a tax question... e.g. What is Section 80C?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if rag_chain is None:
                st.error("RAG Engine not initialized. Please check your setup.")
            else:
                with st.spinner("Thinking..."):
                    response = rag_chain.invoke({"input": prompt})

                message_placeholder = st.empty()
                full_response = ""
                for chunk in response.split(" "):
                    full_response += chunk + " "
                    time.sleep(0.025)
                    message_placeholder.markdown(full_response + "|")
                message_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})

else:
    # ===================== FILING MODE =====================
    filing = st.session_state.filing

    if filing is None:
        # Landing cards
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("""
            <div class="start-card">
                <div class="card-icon">&#9997;</div>
                <div class="card-title">Guided Filing</div>
                <div class="card-desc">AI walks you through every step of your ITR</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown("""
            <div class="start-card">
                <div class="card-icon">&#9878;</div>
                <div class="card-title">Regime Comparison</div>
                <div class="card-desc">Auto-compare Old vs New tax regime</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown("""
            <div class="start-card">
                <div class="card-icon">&#9729;</div>
                <div class="card-title">Save & Resume</div>
                <div class="card-desc">Your progress is saved to the cloud</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # --- Saved Filings (Resume) ---
        saved = list_filings(st.session_state.user_id)
        if saved:
            st.markdown("""
            <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.1em;
                        color: rgba(196, 181, 253, 0.4) !important; margin-bottom: 0.75rem;">
                Resume a Saved Filing
            </div>
            """, unsafe_allow_html=True)

            cols = st.columns(min(len(saved), 3))
            for idx, f in enumerate(saved[:3]):
                name = f['name'] or f['pan'] or 'Draft'
                form = f['form_type'] or 'New'
                step = f.get('current_step', '')
                with cols[idx]:
                    st.markdown(f"""
                    <div class="start-card" style="padding: 1.25rem 1rem; text-align: left;">
                        <div style="font-size: 1rem; font-weight: 600; color: #e2e8f0 !important; margin-bottom: 0.25rem;">{name}</div>
                        <div style="font-size: 0.8rem; color: #a78bfa !important;">{form}</div>
                        <div style="font-size: 0.72rem; color: rgba(255,255,255,0.3) !important; margin-top: 0.35rem;">Step: {step}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    btn_col1, btn_col2 = st.columns([3, 1])
                    with btn_col1:
                        if st.button("Resume", key=f"resume_{f['filing_id']}", use_container_width=True):
                            filing_obj, messages = load_filing(f["filing_id"])
                            st.session_state.filing = filing_obj
                            st.session_state.filing_messages = messages
                            st.session_state.filing_id = f["filing_id"]
                            st.rerun()
                    with btn_col2:
                        st.markdown('<span class="delete-marker"></span>', unsafe_allow_html=True)
                        if st.button("🗑 Delete", key=f"del_{f['filing_id']}", use_container_width=True):
                            delete_filing(f["filing_id"])
                            st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("""
        <div class="info-banner">
            <span class="icon">&#10148;</span>
            Click <strong>Start New Filing</strong> in the sidebar to begin your ITR filing journey.
        </div>
        """, unsafe_allow_html=True)

    else:
        # Active filing -- auto-welcome
        if not st.session_state.filing_messages and filing.current_step == "welcome":
            with st.spinner("Starting your ITR filing..."):
                response, updated_filing, step_advanced = process_filing_message(
                    "I want to file my income tax return.",
                    filing,
                    st.session_state.filing_messages,
                )
            st.session_state.filing = updated_filing
            st.session_state.filing_messages.append({"role": "assistant", "content": response})
            if step_advanced and st.session_state.filing_id:
                update_filing(updated_filing, st.session_state.filing_id, st.session_state.filing_messages)
            filing = updated_filing

        # Step progress bar
        current_label = STEP_LABELS.get(filing.current_step, filing.current_step)
        form_label = filing.form_type or "Determining..."
        steps = FILING_STEPS.get(filing.form_type or "ITR-1", FILING_STEPS["ITR-1"])
        step_idx = steps.index(filing.current_step) + 1 if filing.current_step in steps else 1
        total_steps = len(steps)

        st.progress(step_idx / total_steps, text=f"Step {step_idx}/{total_steps} | {current_label}")

        # Chat history
        for message in st.session_state.filing_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Type your response..."):
            st.session_state.filing_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                rag_context = ""
                if is_tax_question(prompt) and rag_chain is not None:
                    with st.spinner("Looking up tax rules..."):
                        rag_context = rag_chain.invoke({"input": prompt})

                with st.spinner(f"Processing | {current_label}..."):
                    response, updated_filing, step_advanced = process_filing_message(
                        prompt, filing, st.session_state.filing_messages,
                        rag_context=rag_context,
                    )
                st.session_state.filing = updated_filing

                message_placeholder = st.empty()
                full_response = ""
                for chunk in response.split(" "):
                    full_response += chunk + " "
                    time.sleep(0.025)
                    message_placeholder.markdown(full_response + "|")
                message_placeholder.markdown(full_response)
                st.session_state.filing_messages.append({"role": "assistant", "content": full_response})

                if step_advanced:
                    if st.session_state.filing_id:
                        update_filing(updated_filing, st.session_state.filing_id, st.session_state.filing_messages)
                    elif updated_filing.personal.pan:
                        fid = save_filing(updated_filing, st.session_state.user_id, st.session_state.filing_messages)
                        st.session_state.filing_id = fid
                    st.rerun()

# --- 8. DISCLAIMER ---
st.markdown("""
<div class="disclaimer">
    This is an AI research project. Verify all information with the
    <a href="https://www.incometax.gov.in" target="_blank">official Income Tax portal</a>
    or a certified Tax Practitioner.
</div>
""", unsafe_allow_html=True)
