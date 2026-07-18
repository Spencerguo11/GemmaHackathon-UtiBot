# Utility Coordinator AI Assistant

Local-first utility bill processing with Gemma through Ollama, a professional web dashboard with agent activity streaming, and mock provider payment automation.

## Product Overview

Upload a ZIP of utility bill PDFs, watch the local agent work step-by-step (Cursor-style activity panel), review bills in tables, approve mock payments through a permission gate, and view audit reports.

**Privacy:** Bill extraction runs locally through Ollama. Documents are not sent to cloud LLMs.

## Quick Start

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

**Terminal 1 — mock providers (for payment demo):**
```bash
python scripts/run_mock_providers.py
```

**Terminal 2 — web application:**
```bash
python scripts/run_web.py
```

Open **http://localhost:8080**

## Web UI Features

- **Agent Activity panel** — live thinking/tool/success steps streamed during ingestion and payment
- **Bills table** — structured extraction results
- **Payment queue** — prioritized tasks with prepare flow
- **Permission modal** — explicit approve/deny before mock payment submission
- **Audit report** — totals, confirmations, timeline

## Legacy Streamlit UI

Still available but deprecated:

```bash
streamlit run app.py
```

## Tests

```bash
pytest
```

## Configuration

See `.env.example` for `OLLAMA_MODEL`, validation thresholds, and `WEB_PORT`.

## Known Limitations

- Scanned PDFs require review (no OCR)
- Automated Playwright payment targets the electric mock provider
- Gas/water mock sites exist but are not fully automated yet
