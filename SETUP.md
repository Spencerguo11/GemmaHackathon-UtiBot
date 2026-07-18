# 🚀 Utility Coordinator - Setup & Deployment Guide

## Quick Start (5 minutes)

### Prerequisites

- Python 3.11+
- Ollama with Gemma 4 4B already installed and running
- macOS, Linux, or Windows

### 1. Set Up Python Virtual Environment

```bash
cd /path/to/GemmaHackathon-UtiBot

# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate
# On Windows: .venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**Expected time**: 2-3 minutes

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env if you want to change defaults (optional)
```

### 4. Initialize Database

```bash
python scripts/initialize_db.py
```

**Expected output**:
```
Initializing database...
✅ Database initialized successfully!
```

### 5. Verify Ollama Configuration

```bash
python scripts/check_ollama.py
```

**Expected output**:
```
Checking Ollama at http://localhost:11434...
✅ Ollama is running and model 'gemma4:e4b' is available
```

**If Ollama isn't running**:
```bash
# Terminal 1: Start Ollama server
ollama serve

# Terminal 2 (new tab, keep server running):
# Nothing more needed; the model is already pulled
```

### 6. Install Playwright (for Phase 7+)

```bash
playwright install chromium
```

### 7. Launch Streamlit App

```bash
streamlit run app.py
```

Opens at: `http://localhost:8501`

---

## Development Setup

### Verify Project Setup

```bash
python scripts/verify_setup.py
```

This checks:
- ✅ All directories exist
- ✅ All core files present
- ✅ Imports work correctly
- ✅ .env configuration

### Run Tests

```bash
# All tests
pytest -v

# Specific test file
pytest tests/test_zip_handler.py -v

# With coverage
pytest --cov=. --cov-report=html
open htmlcov/index.html
```

### Debug Mode

Enable verbose logging:
```bash
# Edit .env
DEBUG=True

# Then run
streamlit run app.py
```

---

## Project Structure Summary

```
GemmaHackathon-UtiBot/
├── app.py                  # Streamlit app (main entry point)
├── config/                 # Settings & configuration
├── models/                 # Pydantic data models
├── ingestion/              # ZIP, PDF, text extraction
├── services/               # Ollama, validation, extraction
├── database/               # SQLAlchemy ORM & repositories
├── workflows/              # Process orchestration
├── scripts/                # Utilities & setup
├── tests/                  # Unit tests
├── data/                   # Jobs, artifacts, database
├── requirements.txt        # Python dependencies
├── .env.example            # Environment template
└── README.md               # Full documentation
```

## Phase-by-Phase Progress

### ✅ Phase 1-4: COMPLETE

**What's working**:
- Project skeleton and configuration
- Safe ZIP extraction with path traversal protection
- PDF text extraction using PyMuPDF
- Duplicate detection (exact and logical)
- Ollama Gemma client with JSON mode
- Document extraction agent with structured prompts
- Validation service with configurable thresholds
- SQLite database with SQLAlchemy ORM
- Streamlit UI with upload and bill review tabs
- Ingestion workflow orchestration
- Audit logging for all events

**Try it**:
1. Prepare a ZIP file with some utility bill PDFs
2. Run: `streamlit run app.py`
3. Go to 📤 Upload tab
4. Upload your ZIP
5. Watch it extract, validate, and display bills

### ⏳ Phase 5-9: Not Started

**Planned**:
- [ ] Mock provider websites (FastAPI)
- [ ] Playwright browser automation
- [ ] Navigation agent using Gemma
- [ ] Human approval gate
- [ ] Payment verification
- [ ] Audit reporting dashboard

---

## Configuration Reference

### `.env` Settings

```env
# Ollama Configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma4:e4b

# Database
DATABASE_URL=sqlite:///data/utility.db

# Validation Thresholds
MIN_CONFIDENCE=0.85                    # Bills below flagged for review
HIGH_AMOUNT_REVIEW_THRESHOLD=1000      # Amounts above flagged for review

# File Limits
MAX_ZIP_FILES=25                       # Max files per ZIP
MAX_UNCOMPRESSED_MB=100                # Max total size

# Browser Automation (Phase 7+)
MAX_BROWSER_STEPS=15                   # Max steps per payment flow

# Debug
DEBUG=False                            # Verbose logging
```

### `config/provider_registry.yaml`

Edit to add/modify utility providers:
```yaml
Provider Name Demo:
  canonical_name: "Provider Name Demo"
  aliases:
    - "Short Name"
  utility_type: "electricity|gas|water"
  trusted_domains:
    - "localhost:8001"
  payment_url: "http://localhost:8001/pay"
  mock_provider_port: 8001
```

---

## Troubleshooting

### "Ollama not running"

```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Verify model is available
ollama list | grep gemma4

# If not listed:
ollama pull gemma4:e4b
```

### "Cannot connect to Ollama"

Check:
1. Is Ollama running? → `ollama serve`
2. Is it on the right port? → `OLLAMA_HOST=http://localhost:11434` in `.env`
3. Try: `curl http://localhost:11434/api/tags`

### "Model gemma4:e4b not found"

```bash
ollama pull gemma4:e4b
# Wait for download (~3 GB)
python scripts/check_ollama.py
```

### "Database locked"

```bash
# Close any other connections
rm -f data/utility.db-shm data/utility.db-wal
# Retry
```

### "PDF has no embedded text"

Current version doesn't support scanned PDFs (images). Use bills with embedded text.

Planned for Phase 9+: OCR support.

### "Import errors"

Ensure venv is activated:
```bash
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate     # Windows
```

Then reinstall:
```bash
pip install -r requirements.txt
```

### "Port 8501 already in use"

```bash
# Run on different port
streamlit run app.py --server.port 8502
```

---

## Common Commands

```bash
# Activate environment
source .venv/bin/activate

# Initialize database
python scripts/initialize_db.py

# Verify setup
python scripts/verify_setup.py

# Check Ollama status
python scripts/check_ollama.py

# Run tests
pytest -v

# Run tests with coverage
pytest --cov=. --cov-report=html

# Start Streamlit app
streamlit run app.py

# Database inspection
sqlite3 data/utility.db ".schema"
sqlite3 data/utility.db "SELECT COUNT(*) FROM bills;"

# View logs
tail -f data/utility.log  # When logging is configured
```

---

## Next Steps

1. **Test Upload** (5 min):
   - Create a test PDF or use example bill
   - Upload via Streamlit
   - Verify extraction

2. **Explore Database** (10 min):
   - `sqlite3 data/utility.db`
   - Browse tables: `.tables`
   - Query bills: `SELECT * FROM bills;`

3. **Contribute to Phase 5** (N hours):
   - Build FastAPI mock providers
   - Create test payment flows
   - Implement Playwright automation

---

## Project Statistics

**Phase 1-4 Implementation**:
- 30+ Python modules
- 2,000+ lines of core code
- 400+ lines of tests
- 3 data models
- 5 database tables
- Full type hints throughout

**Technology Stack**:
- Python 3.11+
- Streamlit, Ollama, SQLAlchemy, PyMuPDF, Pydantic
- SQLite, Pytest, FastAPI (Phase 5)

---

## Support

- 📖 Read `README.md` for full documentation
- 🧪 Check `tests/` for usage examples
- 🔧 Review `config/settings.py` for all options
- 💬 Enable `DEBUG=True` in `.env` for verbose output

---

**Ready to build the future of local AI! 🚀**
