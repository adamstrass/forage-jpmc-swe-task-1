from __future__ import annotations

import csv
import io
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, send_file

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
LIBRARY_PATH = DATA_DIR / "library.json"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
if not LIBRARY_PATH.exists():
    LIBRARY_PATH.write_text("[]", encoding="utf-8")

app = Flask(__name__)

TAG_KEYWORDS = {
    "hydrogel": ["hydrogel", "gel"],
    "bone graft": ["bone graft", "bone regeneration", "osteoconductive"],
    "biomaterials": ["biomaterial", "polymer", "scaffold"],
    "injectability": ["injectability", "syringe", "extrusion"],
    "rheology": ["rheology", "viscosity", "storage modulus", "loss modulus"],
    "mechanical testing": ["compressive", "tensile", "mechanical"],
    "SEM": ["sem", "scanning electron microscopy", "micrograph"],
    "EDS": ["eds", "energy dispersive"],
    "biocompatibility": ["biocompatibility", "cytotoxicity", "cell viability"],
    "sterilisation": ["sterilisation", "sterilization", "gamma", "eto"],
    "manufacturing": ["manufacturing", "scale-up", "process"],
    "validation": ["validation", "verification", "quality"],
    "regulatory": ["regulatory", "iso", "fda", "ce mark"],
}


def load_library() -> list[dict[str, Any]]:
    return json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))


def save_library(records: list[dict[str, Any]]) -> None:
    LIBRARY_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")


def extract_text_from_pdf(path: Path) -> str:
    if PdfReader is None:
        return "PDF parser unavailable. Install pypdf for full parsing support."
    reader = PdfReader(str(path))
    chunks = []
    for page in reader.pages[:30]:
        chunks.append(page.extract_text() or "")
    return "\n".join(chunks).strip()


def find_year(text: str) -> str:
    hit = re.search(r"\b(19\d{2}|20\d{2})\b", text)
    return hit.group(1) if hit else "Unknown"


def extract_title(text: str, filename: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines:
        return lines[0][:180]
    return Path(filename).stem


def detect_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags = [tag for tag, keys in TAG_KEYWORDS.items() if any(k in lowered for k in keys)]
    return tags[:12] if tags else ["biomaterials"]


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 40]


def top_sentences(text: str, n: int = 3) -> list[str]:
    sents = split_sentences(text)
    return sents[:n] if sents else ["Not enough source text was extracted from this PDF."]


def llm_summary(text: str, filename: str) -> dict[str, Any] | None:
    if OpenAI is None or not os.getenv("OPENAI_API_KEY"):
        return None
    prompt = (
        "You are a scientific intelligence assistant for Tetratherix. "
        "Return JSON only with fields: title, authors, year, journal, main_message, why_matters, "
        "key_findings(array), methods_used, materials_setup, important_numerical_results(array), "
        "conclusions, limitations, tetratherix_implications, relevance_tags(array), quote_worthy(array), "
        "executive_summary, quick_take(array), confidence, extracted_data(object with study_objective, "
        "hypothesis, material_composition, test_methods, controls, statistical_significance, "
        "performance_outcomes, limitations, future_work, claim_strength)."
    )
    client = OpenAI()
    sample = text[:18000]
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Filename: {filename}\n\nDocument text:\n{sample}",
            },
        ],
    )
    raw = response.output_text
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def heuristic_summary(text: str, filename: str) -> dict[str, Any]:
    tags = detect_tags(text)
    evidence = top_sentences(text, 4)
    year = find_year(text)
    title = extract_title(text, filename)

    return {
        "title": title,
        "authors": "Not reliably extracted",
        "year": year,
        "journal": "Not reliably extracted",
        "main_message": top_sentences(text, 1)[0],
        "why_matters": "This paper potentially informs hydrogel design, test strategy, and risk decisions.",
        "key_findings": top_sentences(text, 3),
        "methods_used": "See extracted method-oriented sentences in the source text; recommend manual verification.",
        "materials_setup": "Material details were partially detected from text and should be checked against figures/tables.",
        "important_numerical_results": [
            m.group(0)
            for m in re.finditer(r"\b\d+(?:\.\d+)?\s?(?:%|MPa|kPa|Pa|mL|min|h|days|weeks)\b", text)
        ][:8]
        or ["No clear numeric result captured from extracted text."],
        "conclusions": top_sentences(text, 1)[0],
        "limitations": "Extraction may miss table-heavy or figure-only evidence; confirm with full paper review.",
        "tetratherix_implications": "Potential relevance to synthetic hydrogel handling, mechanical validation, and regulatory evidence building.",
        "relevance_tags": tags,
        "quote_worthy": evidence[:3],
        "executive_summary": " ".join(top_sentences(text, 2)),
        "quick_take": [
            "Paper objective appears aligned with biomaterial performance assessment.",
            "Results include evidence useful for R&D triage and method comparison.",
            "Use caution: confidence depends on text extraction completeness.",
        ],
        "confidence": "Moderate",
        "extracted_data": {
            "study_objective": top_sentences(text, 1)[0],
            "hypothesis": "Not explicitly identified.",
            "material_composition": "Partially detected from extracted text.",
            "test_methods": "Likely includes mechanical/biological characterization; verify manually.",
            "controls": "Not explicitly identified.",
            "statistical_significance": "Not clearly detected.",
            "performance_outcomes": top_sentences(text, 2),
            "limitations": "Automated extraction and OCR gaps may reduce completeness.",
            "future_work": "Validate findings with deeper review and replicate critical methods internally.",
            "claim_strength": "Moderate",
        },
    }


def build_summary(text: str, filename: str) -> dict[str, Any]:
    return llm_summary(text, filename) or heuristic_summary(text, filename)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/upload")
def upload_files():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files supplied."}), 400

    library = load_library()
    created = []

    for file in files:
        doc_id = str(uuid.uuid4())
        saved_name = f"{doc_id}_{file.filename}"
        saved_path = UPLOAD_DIR / saved_name
        file.save(saved_path)

        text = extract_text_from_pdf(saved_path)
        summary = build_summary(text, file.filename)

        record = {
            "id": doc_id,
            "filename": file.filename,
            "saved_path": str(saved_path.relative_to(BASE_DIR)),
            "uploaded_at": datetime.utcnow().isoformat() + "Z",
            "status": "analysed",
            "favorite": False,
            "custom_name": Path(file.filename).stem,
            "summary": summary,
            "raw_text_preview": text[:2500],
            "doc_type": "review" if "review" in text.lower() else "original study",
        }
        library.append(record)
        created.append(record)

    save_library(library)
    return jsonify(created)


@app.get("/api/documents")
def get_documents():
    library = load_library()
    return jsonify(library)


@app.patch("/api/documents/<doc_id>")
def update_document(doc_id: str):
    payload = request.get_json(force=True)
    library = load_library()
    for record in library:
        if record["id"] == doc_id:
            if "custom_name" in payload:
                record["custom_name"] = payload["custom_name"]
            if "favorite" in payload:
                record["favorite"] = bool(payload["favorite"])
            save_library(library)
            return jsonify(record)
    return jsonify({"error": "Document not found"}), 404


@app.post("/api/ask")
def ask_question():
    payload = request.get_json(force=True)
    doc_id = payload.get("doc_id")
    question = payload.get("question", "").strip()

    library = load_library()
    doc = next((item for item in library if item["id"] == doc_id), None)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    summary = doc["summary"]
    q = question.lower()
    if "takeaway" in q or "main" in q:
        answer = summary.get("main_message")
    elif "key result" in q:
        answer = "\n".join(summary.get("key_findings", []))
    elif "material" in q:
        answer = summary.get("materials_setup")
    elif "weakness" in q or "limitation" in q:
        answer = summary.get("limitations")
    elif "injectability" in q:
        answer = summary.get("tetratherix_implications")
    else:
        answer = summary.get("executive_summary")

    return jsonify({"answer": answer, "confidence": summary.get("confidence", "Moderate")})


@app.post("/api/compare")
def compare_documents():
    payload = request.get_json(force=True)
    ids = payload.get("ids", [])
    library = load_library()
    selected = [d for d in library if d["id"] in ids]

    comparison = []
    for doc in selected:
        summary = doc["summary"]
        comparison.append(
            {
                "name": doc["custom_name"],
                "objective": summary["extracted_data"].get("study_objective"),
                "material_system": summary.get("materials_setup"),
                "methods": summary.get("methods_used"),
                "key_findings": summary.get("key_findings"),
                "strengths": summary.get("key_findings", [])[:2],
                "weaknesses": summary.get("limitations"),
                "tetratherix_relevance": summary.get("tetratherix_implications"),
            }
        )
    return jsonify(comparison)


@app.get("/api/export/<doc_id>/csv")
def export_csv(doc_id: str):
    library = load_library()
    doc = next((item for item in library if item["id"] == doc_id), None)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    summary = doc["summary"]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["field", "value"])
    for key, value in summary.items():
        writer.writerow([key, json.dumps(value) if isinstance(value, (dict, list)) else value])
    mem = io.BytesIO(output.getvalue().encode("utf-8"))
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name=f"{doc['custom_name']}_summary.csv")


@app.get("/api/export/<doc_id>/doc")
def export_doc(doc_id: str):
    library = load_library()
    doc = next((item for item in library if item["id"] == doc_id), None)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    summary = doc["summary"]
    body = f"""
    <html><body>
      <h1>{summary.get('title')}</h1>
      <h2>Executive Summary</h2><p>{summary.get('executive_summary')}</p>
      <h2>Main message</h2><p>{summary.get('main_message')}</p>
      <h2>Key findings</h2><ul>{''.join(f'<li>{item}</li>' for item in summary.get('key_findings', []))}</ul>
      <h2>Limitations</h2><p>{summary.get('limitations')}</p>
      <h2>What this means for Tetratherix</h2><p>{summary.get('tetratherix_implications')}</p>
    </body></html>
    """
    mem = io.BytesIO(body.encode("utf-8"))
    return send_file(mem, mimetype="application/msword", as_attachment=True, download_name=f"{doc['custom_name']}.doc")


if __name__ == "__main__":
    app.run(debug=True, port=5050)
