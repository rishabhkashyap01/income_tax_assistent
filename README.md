# TaxAI — Smart ITR Filing Assistant

An AI-powered Indian Income Tax Return filing assistant built with Streamlit, LangChain, and Groq. It combines a RAG-based Q&A engine (trained on 518 Income Tax Rules) with a guided conversational ITR filing flow supporting ITR-1 through ITR-4.

## Features

- **Conversational ITR Filing** — AI guides you step-by-step through the entire ITR filing process (personal info, income sources, deductions, tax computation, and summary)
- **Multi-Form Support** — Supports ITR-1 (salaried), ITR-2 (capital gains), ITR-3 (business/profession), and ITR-4 (presumptive income)
- **RAG-Powered Q&A** — Ask any question about the Income Tax Act 1961 or Rules 1962 and get accurate, source-grounded answers
- **Hybrid Retrieval** — Combines metadata-filtered search (exact rule/section lookup) with semantic MMR search for high accuracy
- **Old vs New Regime Comparison** — Automatically computes and compares tax liability under both regimes with a recommendation
- **User Authentication** — Register/login system with bcrypt password hashing
- **MongoDB Persistence** — All filings and chat history are saved to MongoDB Atlas, scoped per user
- **Save & Resume** — Save filing progress at any point, come back later and resume with full chat history restored
- **Modern UI** — Clean, minimalist interface with gradient sidebar, progress tracking, and animated chat

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit |
| LLM | Groq (Llama 3.3 70B) |
| RAG Framework | LangChain |
| Vector Database | ChromaDB |
| Embeddings | HuggingFace (`all-MiniLM-L6-v2`) |
| Database | MongoDB Atlas |
| Authentication | bcrypt |
| Data Scraping | BeautifulSoup, Crawl4AI, Playwright |

## Project Structure

```
income_tax_assistent/
├── app.py                    # Streamlit app (auth gate, Q&A mode, filing mode)
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (API keys, DB config)
├── .gitignore
├── .streamlit/
│   └── config.toml           # Streamlit config (file watcher fix for Windows)
├── src/
│   ├── auth.py               # User registration & login (bcrypt)
│   ├── database.py           # MongoDB connection singleton & indexes
│   ├── filing_engine.py      # LLM-driven filing flow (prompt building, data extraction)
│   ├── filing_storage.py     # Filing CRUD operations (MongoDB)
│   ├── itr_models.py         # Data models for ITR forms (Python dataclasses)
│   ├── itr_prompts.py        # Step-specific system prompts for each ITR form
│   ├── rag_engine.py         # RAG chain with hybrid retrieval
│   ├── tax_engine.py         # Tax computation engine (Old & New regime, AY 2025-26)
│   ├── ingest.py             # Ingest Income Tax Act PDF into ChromaDB
│   ├── ingest_rules.py       # Ingest scraped rules markdown into ChromaDB
│   └── ingest2.py            # Additional ingestion utilities
├── scrapers/
│   ├── incomeTaxActScraper.py    # Scraper for Income Tax Act sections
│   ├── incomeTaxRuleScraper.py   # Scraper for individual rules
│   └── scrape_all_rules.py       # Batch scraper for all 518 rules
└── data/
    ├── chroma_db/            # ChromaDB vector store (auto-generated)
    ├── raw_pdf/              # Income Tax Act 1961 PDF
    ├── raw_markdown/         # Scraped markdown files
    │   └── rules/            # 518 individual rule files (rule_1.md, rule_2A.md, ...)
    └── rules_index.json      # Rule number → URL index
```

## Setup

### Prerequisites

- Python 3.10+
- A [Groq API key](https://console.groq.com/) (free tier available)
- A [MongoDB Atlas](https://www.mongodb.com/atlas) account (free tier works)

### 1. Clone the repository

```bash
git clone https://github.com/your-username/income_tax_assistent.git
cd income_tax_assistent
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
pip install "pymongo[srv]"
```

The `[srv]` extra installs `dnspython`, required for `mongodb+srv://` Atlas connection strings.

### 3. Set up the `.env` file

Create a `.env` file in the project root with the following variables:

```env
# Groq LLM API Key
# Get yours at https://console.groq.com/
GROQ_API_KEY=gsk_your_groq_api_key_here

# MongoDB Atlas Connection
# 1. Create a free cluster at https://www.mongodb.com/atlas
# 2. Go to Database > Connect > Drivers > Python
# 3. Copy the connection string and replace <username>, <password>, and cluster URL
# 4. Under Network Access, add your IP (or 0.0.0.0/0 for development)
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority

# Database name (can be anything you want)
MONGO_DB_NAME=tax_assistant
```

### 4. Build the knowledge base

The ChromaDB vector store needs to be populated before the Q&A engine works. If `data/chroma_db/` doesn't already exist:

```bash
# Scrape all 518 rules from the Income Tax website
python scrapers/scrape_all_rules.py

# Ingest the Income Tax Act PDF
python src/ingest.py

# Ingest the scraped rules with metadata
python src/ingest_rules.py
```

### 5. Run the app

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`. Register an account and you're ready to go.

## Usage

### Q&A Mode
Ask any question about Indian income tax — sections, rules, deductions, exemptions, or filing procedures. The RAG engine retrieves relevant rules and generates grounded answers.

### Filing Mode
Click **Start New Filing** in the sidebar. The AI will guide you through:

1. **Welcome** — Determines your ITR form type based on your income sources
2. **Personal Info** — PAN, name, DOB, address, contact details
3. **Income Sources** — Salary, house property, capital gains, business income (form-dependent)
4. **Deductions** — 80C, 80D, 80G, HRA, and other eligible deductions
5. **Tax Payments** — TDS, advance tax, self-assessment tax
6. **Bank Details** — Refund bank account
7. **Regime Comparison** — Side-by-side Old vs New regime tax computation
8. **Summary** — Final review of the complete filing

Progress is auto-saved to MongoDB. You can exit and resume any filing later with full chat history.

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | API key from [Groq Console](https://console.groq.com/) |
| `MONGO_URI` | Yes | MongoDB Atlas connection string |
| `MONGO_DB_NAME` | No | Database name (defaults to `tax_assistant`) |
