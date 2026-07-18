# 🔌 Utility Coordinator AI Assistant

A hackathon MVP for locally processing utility bills using Gemma 4 through Ollama, with mock provider payment automation.

**Key Feature**: All AI reasoning and bill processing runs locally. No cloud APIs. No real payments.

## 🎯 Product Overview

Upload a ZIP of utility bills → Extract structured data with local Gemma → Review and edit in dashboard → Test payment workflows on mock providers → Generate audit report.

### MVP Capabilities

- ✅ **Phase 1-4 COMPLETE**: ZIP upload → PDF extraction → Gemma analysis → Streamlit dashboard
- ⏳ Phase 5-9: Mock providers, browser automation, payment testing, audit reporting

## 🏗️ Architecture

```
utility-coordinator/
├── app.py                      # Streamlit UI
├── config/                     # Settings & provider registry
├── models/                     # Pydantic data models
├── ingestion/                  # ZIP, PDF, text processing
├── services/                   # Ollama, validation, extraction
├── database/                   # SQLAlchemy ORM & repos
├── workflows/                  # Process orchestration
├── browser/                    # (Phase 7) Playwright automation
├── agents/                     # (Phase 7) Navigation & verification
├── mock_providers/             # (Phase 5) FastAPI mock sites
├── scripts/                    # Utilities & initialization
├── tests/                      # Unit tests
└── data/                       # Jobs & artifacts
```

## 🚀 Quick Start

### 1. Set Up Python Environment

```bash
cd GemmaHackathon-UtiBot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

### 3. Initialize Database

```bash
python scripts/initialize_db.py
```

### 4. Verify Ollama & Gemma 4

```bash
python scripts/check_ollama.py
```

If not running:
```bash
ollama serve  # Terminal 1
ollama pull gemma4:e4b  # Terminal 2
```

### 5. Start Streamlit

```bash
streamlit run app.py
```

Opens at: `http://localhost:8501`

## 📚 How to Use

1. **Upload**: Click 📤 tab, select ZIP with PDFs, click 🚀
2. **Review**: Click 📋 tab, see extracted bills
3. **Payment** (Phase 5+): Click 💰 tab
4. **Report** (Phase 8+): Click 📊 tab

## 📊 Data Models

- **Bill**: provider_name, utility_type, account_masked, amount_due, due_date, status
- **PaymentTask**: bill_id, priority, status, approval
- **Transaction**: confirmation_number, amount, verification_status
- **AuditEvent**: Comprehensive logging of all actions

## 🔒 Safety

- ✅ Local processing only (no cloud LLMs)
- ✅ Safe ZIP extraction (no path traversal)
- ✅ Human approval gate required
- ✅ No real credentials or payments
- ✅ Mock providers on localhost only

## 📁 Implementation Status

### ✅ Phase 1-4: COMPLETE

- [x] Project skeleton
- [x] Settings & configuration
- [x] Pydantic models
- [x] SQLAlchemy ORM
- [x] Safe ZIP extraction
- [x] PDF extraction
- [x] Duplicate detection
- [x] Ollama client
- [x] Document extraction agent
- [x] Validation service
- [x] SQLite repositories
- [x] Streamlit UI
- [x] Ingestion workflow

### ⏳ Phase 5-9: Mock Providers, Automation, Reporting

## 🧪 Testing

```bash
pytest -v                          # Run all tests
pytest tests/test_zip_handler.py   # Run specific test
pytest --cov=.                     # Coverage report
```

## 🔧 Configuration

Edit `.env`:

```env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma4:e4b
DATABASE_URL=sqlite:///data/utility.db
MIN_CONFIDENCE=0.85
HIGH_AMOUNT_REVIEW_THRESHOLD=1000
MAX_ZIP_FILES=25
MAX_UNCOMPRESSED_MB=100
MAX_BROWSER_STEPS=15
DEBUG=False
```

## 📞 Troubleshooting

**Ollama not running**: `ollama serve`

**Model not found**: `ollama pull gemma4:e4b`

**Database locked**: Delete `data/utility.db-shm` and retry

**PDF has no text**: Scanned PDFs not supported yet (Phase 9+)

## 📖 Architecture Layers

1. **Ingestion**: ZIP → PDF extraction → text cleaning → duplicate detection
2. **AI Services**: Ollama client → document extraction → validation
3. **Database**: SQLAlchemy ORM → repositories → SQLite
4. **Workflow**: Orchestration of entire process
5. **UI**: Streamlit dashboard with tabs
6. **Browser** (Phase 7): Playwright automation → navigation agents
7. **Mock Providers** (Phase 5): FastAPI local websites

## 🎯 Next Steps

1. Phase 5: Build three mock provider FastAPI apps
2. Phase 6: Playwright automation for electric provider
3. Phase 7: Safety layer (page observer, navigation agent)
4. Phase 8: Human approval UI and verification
5. Phase 9: Tests and polish

---

**Built with Gemma 4, Ollama, and ❤️**
