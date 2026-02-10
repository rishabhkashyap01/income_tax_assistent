import streamlit as st
import time
import os
from src.rag_engine import get_rag_chain
from src.itr_models import ITRFiling
from src.itr_prompts import FILING_STEPS, STEP_LABELS
from src.filing_engine import process_filing_message, is_tax_question
from src.filing_storage import save_filing, save_filing_to_path, load_filing, list_filings

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="TaxAI — Smart ITR Filing",
    page_icon="\U0001f4b0",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- 2. MODERN CSS ---
st.markdown("""
<style>
/* ─── Global ─── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

:root {
    --bg: #f8fafc;
    --surface: #ffffff;
    --surface-hover: #f1f5f9;
    --border: #e2e8f0;
    --border-light: #f1f5f9;
    --text: #0f172a;
    --text-secondary: #64748b;
    --text-muted: #94a3b8;
    --accent: #6366f1;
    --accent-light: #eef2ff;
    --accent-dark: #4f46e5;
    --success: #10b981;
    --success-light: #ecfdf5;
    --warning: #f59e0b;
    --gradient-start: #6366f1;
    --gradient-end: #8b5cf6;
}

.stApp {
    background-color: var(--bg) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* ─── Hide Streamlit defaults ─── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* ─── Sidebar ─── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1e1b4b 0%, #312e81 100%) !important;
    border-right: none !important;
}

section[data-testid="stSidebar"] * {
    color: #e0e7ff !important;
}

section[data-testid="stSidebar"] .stRadio label span {
    color: #c7d2fe !important;
    font-weight: 500 !important;
}

section[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.1) !important;
}

section[data-testid="stSidebar"] .stButton button {
    background: rgba(255,255,255,0.1) !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
    color: #e0e7ff !important;
    border-radius: 10px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}

section[data-testid="stSidebar"] .stButton button:hover {
    background: rgba(255,255,255,0.2) !important;
    border-color: rgba(255,255,255,0.3) !important;
    transform: translateY(-1px) !important;
}

section[data-testid="stSidebar"] .stButton button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    border: none !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3) !important;
}

section[data-testid="stSidebar"] .stButton button[kind="primary"]:hover {
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.5) !important;
}

/* ─── Hero Header ─── */
.hero {
    text-align: center;
    padding: 1.5rem 0 1rem;
}

.hero-title {
    font-size: 2rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--gradient-start), var(--gradient-end));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.25rem;
    letter-spacing: -0.02em;
}

.hero-subtitle {
    font-size: 0.95rem;
    color: var(--text-secondary);
    font-weight: 400;
}

/* ─── Mode Pill Tabs ─── */
.mode-pills {
    display: flex;
    gap: 0.5rem;
    justify-content: center;
    margin: 0.75rem 0 1.25rem;
}

.mode-pill {
    padding: 0.5rem 1.5rem;
    border-radius: 100px;
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.25s ease;
    text-decoration: none;
    border: 1.5px solid var(--border);
    color: var(--text-secondary);
    background: var(--surface);
}

.mode-pill.active {
    background: linear-gradient(135deg, var(--gradient-start), var(--gradient-end));
    color: white;
    border-color: transparent;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25);
}

/* ─── Info Banner ─── */
.info-banner {
    background: var(--accent-light);
    border: 1px solid #c7d2fe;
    border-radius: 12px;
    padding: 0.85rem 1.25rem;
    font-size: 0.88rem;
    color: var(--accent-dark);
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.info-banner .icon { font-size: 1.1rem; }

/* ─── Chat Messages ─── */
[data-testid="stChatMessage"] {
    background: var(--surface) !important;
    border: 1px solid var(--border-light) !important;
    border-radius: 16px !important;
    padding: 1rem 1.25rem !important;
    margin-bottom: 0.75rem !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    transition: box-shadow 0.2s ease !important;
}

[data-testid="stChatMessage"]:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
}

[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] div,
[data-testid="stChatMessage"] li {
    color: var(--text) !important;
    font-size: 0.92rem !important;
    line-height: 1.65 !important;
}

/* ─── Chat Input ─── */
[data-testid="stChatInput"] {
    border-radius: 16px !important;
    border: 2px solid var(--border) !important;
    background: var(--surface) !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}

[data-testid="stChatInput"]:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1) !important;
}

/* ─── Progress Bar ─── */
.stProgress > div > div {
    background: linear-gradient(90deg, var(--gradient-start), var(--gradient-end)) !important;
    border-radius: 100px !important;
}

.stProgress > div {
    background: var(--border-light) !important;
    border-radius: 100px !important;
}

/* ─── Filing Progress Steps (sidebar) ─── */
.step-item {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding: 0.4rem 0.75rem;
    margin: 0.15rem 0;
    border-radius: 8px;
    font-size: 0.82rem;
    transition: background 0.15s ease;
}

.step-item.completed {
    color: #86efac !important;
}

.step-item.completed .step-icon {
    background: rgba(16, 185, 129, 0.2);
    color: #34d399;
}

.step-item.current {
    background: rgba(255,255,255,0.1);
    color: #ffffff !important;
    font-weight: 600;
}

.step-item.current .step-icon {
    background: rgba(99, 102, 241, 0.3);
    color: #a5b4fc;
}

.step-item.pending {
    color: rgba(255,255,255,0.4) !important;
}

.step-icon {
    width: 22px;
    height: 22px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.7rem;
    flex-shrink: 0;
}

/* ─── Filing Start Cards ─── */
.start-card {
    background: var(--surface);
    border: 1.5px solid var(--border);
    border-radius: 16px;
    padding: 2rem;
    text-align: center;
    transition: all 0.2s ease;
    cursor: pointer;
}

.start-card:hover {
    border-color: var(--accent);
    box-shadow: 0 4px 20px rgba(99, 102, 241, 0.1);
    transform: translateY(-2px);
}

.start-card .card-icon {
    font-size: 2.5rem;
    margin-bottom: 0.75rem;
}

.start-card .card-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 0.25rem;
}

.start-card .card-desc {
    font-size: 0.85rem;
    color: var(--text-secondary);
}

/* ─── Sidebar Status Badge ─── */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.35rem 0.85rem;
    border-radius: 100px;
    font-size: 0.78rem;
    font-weight: 500;
}

.status-badge.connected {
    background: rgba(16, 185, 129, 0.15);
    color: #34d399;
}

/* ─── Stat card ─── */
.stat-card {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    padding: 0.85rem 1rem;
    margin-top: 0.75rem;
}

.stat-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: rgba(255,255,255,0.5) !important;
    margin-bottom: 0.2rem;
}

.stat-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: #ffffff !important;
}

/* ─── Disclaimer ─── */
.disclaimer {
    text-align: center;
    padding: 1rem 0 0.5rem;
    font-size: 0.75rem;
    color: var(--text-muted);
    border-top: 1px solid var(--border-light);
    margin-top: 1.5rem;
}

/* ─── Spinner ─── */
.stSpinner > div {
    border-top-color: var(--accent) !important;
}

/* ─── Scrollbar ─── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
</style>
""", unsafe_allow_html=True)


# --- 3. INITIALIZE RAG ENGINE (Cached) ---
@st.cache_resource
def init_rag():
    try:
        return get_rag_chain()
    except Exception as e:
        st.error(f"Error loading RAG Engine: {e}")
        return None

rag_chain = init_rag()

# --- 4. SESSION STATE INIT ---
if "mode" not in st.session_state:
    st.session_state.mode = "qa"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "filing" not in st.session_state:
    st.session_state.filing = None
if "filing_messages" not in st.session_state:
    st.session_state.filing_messages = []
if "filing_path" not in st.session_state:
    st.session_state.filing_path = None

# --- 5. SIDEBAR ---
with st.sidebar:
    # Logo & Brand
    st.markdown("""
    <div style="text-align:center; padding: 1.25rem 0 0.5rem;">
        <div style="font-size: 2.25rem; margin-bottom: 0.25rem;">💰</div>
        <div style="font-size: 1.15rem; font-weight: 700; color: #ffffff !important; letter-spacing: -0.01em;">TaxAI</div>
        <div style="font-size: 0.72rem; color: rgba(255,255,255,0.5) !important; letter-spacing: 0.05em; text-transform: uppercase;">Smart ITR Filing</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Mode selector
    mode = st.radio(
        "Mode",
        ["\U0001f4ac  Q&A Assistant", "\U0001f4cb  File ITR"],
        index=0 if st.session_state.mode == "qa" else 1,
        label_visibility="collapsed",
    )
    st.session_state.mode = "qa" if "Q&A" in mode else "filing"

    st.markdown("---")

    if st.session_state.mode == "qa":
        # ── Q&A sidebar ──
        if os.path.exists("data/chroma_db"):
            st.markdown("""
            <div class="status-badge connected">
                <span>\u2022</span> Knowledge Base Active
            </div>
            """, unsafe_allow_html=True)

            rule_count = len(os.listdir("data/raw_markdown/rules")) if os.path.exists("data/raw_markdown/rules") else 0
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-label">Rules Indexed</div>
                <div class="stat-value">{rule_count}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.warning("Knowledge Base not found")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("\U0001f5d1  Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    else:
        # ── Filing sidebar ──
        filing = st.session_state.filing

        if filing is None:
            st.markdown("""
            <div style="text-align:center; padding: 1rem 0; color: rgba(255,255,255,0.6) !important; font-size: 0.85rem;">
                Start a new filing or<br>resume a saved one
            </div>
            """, unsafe_allow_html=True)

            if st.button("\u2728  Start New Filing", type="primary", use_container_width=True):
                st.session_state.filing = ITRFiling()
                st.session_state.filing_messages = []
                st.session_state.filing_path = None
                st.rerun()

            saved = list_filings()
            if saved:
                st.markdown("---")
                st.markdown("""
                <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: rgba(255,255,255,0.4) !important; margin-bottom: 0.5rem;">
                    Saved Filings
                </div>
                """, unsafe_allow_html=True)
                for f in saved[:5]:
                    name = f['name'] or f['pan'] or 'Draft'
                    form = f['form_type'] or 'New'
                    label = f"{name} \u00b7 {form}"
                    if st.button(label, key=f["filepath"], use_container_width=True):
                        st.session_state.filing = load_filing(f["filepath"])
                        st.session_state.filing_messages = []
                        st.session_state.filing_path = f["filepath"]
                        st.rerun()
        else:
            # Active filing — progress tracker
            form_type = filing.form_type or "ITR-1"
            steps = FILING_STEPS.get(form_type, FILING_STEPS["ITR-1"])
            completed_count = len(filing.completed_steps)
            total = len(steps)

            st.markdown(f"""
            <div style="text-align:center; margin-bottom: 0.75rem;">
                <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: rgba(255,255,255,0.4) !important;">Filing Progress</div>
                <div style="font-size: 1.75rem; font-weight: 700; color: #ffffff !important;">{completed_count}/{total}</div>
                <div style="font-size: 0.78rem; color: rgba(255,255,255,0.5) !important;">{form_type or 'Determining...'}</div>
            </div>
            """, unsafe_allow_html=True)

            for step in steps:
                label = STEP_LABELS.get(step, step)
                if step in filing.completed_steps:
                    st.markdown(f"""<div class="step-item completed"><span class="step-icon">\u2713</span>{label}</div>""", unsafe_allow_html=True)
                elif step == filing.current_step:
                    st.markdown(f"""<div class="step-item current"><span class="step-icon">\u25B6</span>{label}</div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""<div class="step-item pending"><span class="step-icon">\u00b7</span>{label}</div>""", unsafe_allow_html=True)

            st.markdown("---")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("\U0001f4be Save", use_container_width=True):
                    if st.session_state.filing_path:
                        save_filing_to_path(filing, st.session_state.filing_path)
                    else:
                        path = save_filing(filing)
                        st.session_state.filing_path = path
                    st.toast("Progress saved!", icon="\u2705")

            with col2:
                if st.button("\u2716 Exit", use_container_width=True):
                    if st.session_state.filing_path:
                        save_filing_to_path(filing, st.session_state.filing_path)
                    elif filing.personal.pan:
                        path = save_filing(filing)
                        st.session_state.filing_path = path
                    st.session_state.filing = None
                    st.session_state.filing_messages = []
                    st.session_state.filing_path = None
                    st.rerun()


# --- 6. MAIN CONTENT ---

# Hero
st.markdown("""
<div class="hero">
    <div class="hero-title">TaxAI Assistant</div>
    <div class="hero-subtitle">Your intelligent companion for Indian Income Tax</div>
</div>
""", unsafe_allow_html=True)


if st.session_state.mode == "qa":
    # ===================== Q&A MODE =====================
    st.markdown("""
    <div class="info-banner">
        <span class="icon">\U0001f4a1</span>
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
                    message_placeholder.markdown(full_response + "\u258c")
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
                <div class="card-icon">\U0001f4dd</div>
                <div class="card-title">Guided Filing</div>
                <div class="card-desc">AI walks you through every step of your ITR</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown("""
            <div class="start-card">
                <div class="card-icon">\U0001f4ca</div>
                <div class="card-title">Regime Comparison</div>
                <div class="card-desc">Auto-compare Old vs New tax regime</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown("""
            <div class="start-card">
                <div class="card-icon">\U0001f4be</div>
                <div class="card-title">Save & Resume</div>
                <div class="card-desc">Your progress is saved automatically</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div class="info-banner">
            <span class="icon">\U0001f449</span>
            Click <strong>Start New Filing</strong> in the sidebar to begin your ITR filing journey.
        </div>
        """, unsafe_allow_html=True)

    else:
        # Active filing — auto-welcome
        if not st.session_state.filing_messages and filing.current_step == "welcome":
            with st.spinner("Starting your ITR filing..."):
                response, updated_filing, step_advanced = process_filing_message(
                    "I want to file my income tax return.",
                    filing,
                    st.session_state.filing_messages,
                )
            st.session_state.filing = updated_filing
            st.session_state.filing_messages.append({"role": "assistant", "content": response})
            if step_advanced and st.session_state.filing_path:
                save_filing_to_path(updated_filing, st.session_state.filing_path)
            filing = updated_filing

        # Step progress bar
        current_label = STEP_LABELS.get(filing.current_step, filing.current_step)
        form_label = filing.form_type or "Determining..."
        steps = FILING_STEPS.get(filing.form_type or "ITR-1", FILING_STEPS["ITR-1"])
        step_idx = steps.index(filing.current_step) + 1 if filing.current_step in steps else 1
        total_steps = len(steps)

        st.progress(step_idx / total_steps, text=f"Step {step_idx}/{total_steps} \u00b7 {current_label}")

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

                with st.spinner(f"Processing \u00b7 {current_label}..."):
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
                    message_placeholder.markdown(full_response + "\u258c")
                message_placeholder.markdown(full_response)
                st.session_state.filing_messages.append({"role": "assistant", "content": full_response})

                if step_advanced:
                    if st.session_state.filing_path:
                        save_filing_to_path(updated_filing, st.session_state.filing_path)
                    elif updated_filing.personal.pan:
                        path = save_filing(updated_filing)
                        st.session_state.filing_path = path
                    st.rerun()

# --- 7. DISCLAIMER ---
st.markdown("""
<div class="disclaimer">
    \u26A0\uFE0F This is an AI research project. Verify all information with the
    <a href="https://www.incometax.gov.in" target="_blank" style="color: var(--accent);">official Income Tax portal</a>
    or a certified Tax Practitioner.
</div>
""", unsafe_allow_html=True)
