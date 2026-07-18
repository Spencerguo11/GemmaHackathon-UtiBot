# Utility Coordinator AI Assistant

Local-first utility bill processing with Gemma through Ollama, Streamlit review, and mock provider payment automation.

## Product Overview

Upload a ZIP of utility bill PDFs, extract structured data with on-device Gemma, review and edit results, prioritize payment tasks, and test a safe mock payment workflow on localhost provider sites.

**Privacy:** Bill extraction and AI reasoning run locally through Ollama. Bill documents are not sent to a cloud-hosted LLM. Mock provider interactions remain on localhost.

## Architecture

```text
app.py                 Streamlit dashboard
config/                Settings + provider registry
models/                Pydantic domain models
ingestion/             ZIP, PDF, duplicate detection
agents/                Document, navigation, verification agents
services/              Ollama client, validation, payment, audit
database/              SQLAlchemy ORM + repositories
workflows/             Ingestion + payment orchestration
browser/               Playwright observer/executor
mock_providers/        FastAPI demo utility sites
scripts/               Setup and runtime helpers
tests/                 Unit tests (Ollama mocked/not required)
```

## Safety Boundaries

- No real utility providers, credentials, or financial transactions
- Trusted payment URLs come only from `config/provider_registry.yaml`
- Human approval is required before final mock payment submission
- Browser actions are restricted to structured action types

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/)
- Local Gemma model: `gemma4:e4b`

## Setup

```bash
cd GemmaHackathon-UtiBot
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
python scripts/initialize_db.py
python scripts/check_ollama.py
```

If Ollama is not running:

```bash
ollama serve
ollama pull gemma4:e4b
```

## Run the App

Terminal 1 – mock providers:

```bash
python scripts/run_mock_providers.py
```

Terminal 2 – Streamlit:

```bash
streamlit run app.py
```

Open `http://localhost:8501`.

## Demo Workflow

1. Upload a ZIP containing PDF utility bills.
2. Review extracted bills in the **Bills** tab and edit fields if needed.
3. Open **Payment Queue**, choose a `ready` electric bill task.
4. Click **Prepare mock payment** to reach the review step.
5. Approve or cancel at the human approval gate.
6. View confirmations, screenshots, and audit events in **Report**.

Mock provider demo credentials (gas site): `demo` / `demo123`

## Tests

```bash
pytest
```

## Configuration

Environment variables (see `.env.example`):

```env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma4:e4b
DATABASE_URL=sqlite:///data/utility.db
MIN_CONFIDENCE=0.85
HIGH_AMOUNT_REVIEW_THRESHOLD=1000
MAX_ZIP_FILES=25
MAX_UNCOMPRESSED_MB=100
MAX_BROWSER_STEPS=15
```

## Known Limitations

- Scanned/image-only PDFs are flagged for review (no OCR in MVP)
- Automated Playwright payment flow is implemented for the electric mock provider
- Gas and water mock sites are available but not fully automated yet
- Navigation agent uses deterministic safety rules for the demo electric flow

## Future Enhancements

- OCR for scanned bills
- Full LLM-assisted navigation for gas/water providers
- Receipt PDF export and richer audit analytics
