# Tetratherix Scientific Intelligence Web App

A clean, professional internal web app for uploading and analysing PDF journal articles, technical papers, reports, and internal scientific documents.

## Features

- Multi-PDF upload with drag-and-drop + file picker.
- Upload progress and status indicators.
- Structured AI-driven summary for each PDF:
  - Title, authors, year, source
  - Main message and why it matters
  - Key findings, methods, setup, numerical results
  - Conclusions, limitations, confidence level
  - Quote-worthy evidence
  - Executive summary + 3-bullet quick take
  - Relevance tags
- Scientific intelligence extraction:
  - Objective, hypothesis, material composition, methods, controls
  - Statistical significance, outcomes, limitations, future work
  - Claim strength assessment
- Dedicated **"What this means for Tetratherix"** interpretation.
- Chat-style Q&A for each document.
- Side-by-side comparison for selected papers.
- Search/filter by keyword, year, tag, type.
- Library/history with rename + favourite toggle.
- Export summary to Word/CSV and printable PDF.

## Stack

- Frontend: HTML/CSS/vanilla JS (single-page UI)
- Backend: Flask (Python)
- Parsing: `pypdf`
- LLM summarisation: OpenAI API (optional, via `OPENAI_API_KEY`)
- Storage: local JSON + uploaded files

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:5050`.

## Notes

- If OpenAI credentials are unavailable, the app uses a local heuristic summariser.
- This app is intended for scientific triage and should be paired with manual expert review.
