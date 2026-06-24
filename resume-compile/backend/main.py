"""
Resume AI Editor — Backend
FastAPI server: file parsing, AI analysis, LaTeX compilation, model management.
"""
import json
import logging
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pdfminer.high_level import extract_text as pdf_extract_text

load_dotenv(override=True)

# ── Logging ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"resume-editor.{datetime.now().strftime('%Y-%m-%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(log_file), encoding="utf-8"),
    ],
)
logger = logging.getLogger("resume-editor")

app = FastAPI(title="Resume AI Editor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR = BASE_DIR / "tectonic-cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
MODELS_FILE = BASE_DIR / "models.json"

SYSTEM_PROMPT = """You are a professional resume consultant and career coach.
You analyze resumes against job descriptions, provide honest assessments,
and suggest improvements. Always be direct and actionable.

When analyzing gaps: be specific about what's missing vs what can be repackaged.
When assessing: score realistically and explain why.
When suggesting remediation: give concrete learning resources and timelines.
When rewriting: maintain truthful framing while maximizing impact."""

# ── Model Management ────────────────────────────────────────────────────

def _clean(s: str) -> str:
    """Strip ANSI escape codes and trim whitespace from a string."""
    return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', s).strip()


def load_models() -> list:
    """Load model configs. Env default + user-added from models.json."""
    models = []
    # Default model from .env
    env_key = os.getenv("ANTHROPIC_API_KEY")
    env_model = _clean(os.getenv("MODEL_ID", ""))
    env_base = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    if env_key and env_model:
        models.append({
            "id": env_model,
            "name": env_model,
            "api_key": env_key,
            "base_url": env_base,
            "default": True,
        })
    # User-added models from models.json
    if MODELS_FILE.exists():
        try:
            extra = json.loads(MODELS_FILE.read_text())
            if isinstance(extra, list):
                # Append non-duplicate user models
                existing_ids = {m["id"] for m in models}
                for m in extra:
                    m["id"] = _clean(m.get("id", ""))
                    m["name"] = _clean(m.get("name", ""))
                    m["base_url"] = _clean(m.get("base_url", ""))
                    if m["id"] and m["id"] not in existing_ids:
                        m["default"] = False
                        models.append(m)
        except (json.JSONDecodeError, KeyError):
            pass
    return models


def save_user_model(model: dict):
    """Save a user-added model to models.json."""
    existing = []
    if MODELS_FILE.exists():
        try:
            existing = json.loads(MODELS_FILE.read_text())
        except json.JSONDecodeError:
            existing = []
    # Remove old entry with same id
    existing = [m for m in existing if m.get("id") != model["id"]]
    existing.append(model)
    MODELS_FILE.write_text(json.dumps(existing, indent=2))


def remove_user_model(model_id: str):
    """Remove a user-added model."""
    if not MODELS_FILE.exists():
        return
    try:
        existing = json.loads(MODELS_FILE.read_text())
        existing = [m for m in existing if m.get("id") != model_id]
        MODELS_FILE.write_text(json.dumps(existing, indent=2))
    except json.JSONDecodeError:
        pass


def get_model(model_id: str) -> Optional[dict]:
    """Find a model config by ID."""
    for m in load_models():
        if m["id"] == model_id:
            return m
    return None


async def _call_claude(model_cfg: dict, system: str, messages: list, max_tokens: int = 4096) -> tuple[str, str, bool]:
    """Call an Anthropic-compatible API asynchronously.
    Returns (thinking_text, answer_text, was_truncated).
    """
    model_id = model_cfg["id"]
    logger.info("AI call start: model=%s max_tokens=%d", model_id, max_tokens)
    client = AsyncAnthropic(
        api_key=model_cfg["api_key"],
        base_url=model_cfg.get("base_url", "https://api.anthropic.com"),
    )
    try:
        resp = await client.messages.create(
            model=model_id,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
        )
    except Exception as e:
        logger.error("AI call failed: model=%s error=%s", model_id, str(e)[:200])
        raise HTTPException(502, f"AI call failed: {str(e)[:200]}")

    truncated = resp.stop_reason == "max_tokens"

    thinking_parts = []
    text_parts = []
    for block in resp.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "thinking":
            thinking_parts.append(block.thinking)

    thinking = "\n".join(thinking_parts)
    text = "\n".join(text_parts)

    if not text and not thinking:
        logger.warning("AI response has no extractable content: model=%s", model_id)
        raise HTTPException(502, "Model response contains no extractable content")

    logger.info("AI call ok: model=%s thinking=%d text=%d truncated=%s",
                model_id, len(thinking), len(text), truncated)
    return thinking, text, truncated


# ── Parsing ────────────────────────────────────────────────────────────

def parse_pdf(path: Path) -> str:
    return pdf_extract_text(str(path))


def parse_docx(path: Path) -> str:
    from docx import Document
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def parse_latex(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ── Model Routes ────────────────────────────────────────────────────────

@app.get("/api/models")
def list_models():
    """List all available models (env default + user-added)."""
    raw = load_models()
    # Strip api_key from response for security
    safe = []
    for m in raw:
        safe.append({k: v for k, v in m.items() if k != "api_key"})
    return {"models": safe}


@app.post("/api/models/validate")
async def validate_model(
    api_key: str = Form(...),
    base_url: str = Form(...),
    model_id: str = Form(...),
):
    """Test a model config with a simple API call."""
    try:
        client = AsyncAnthropic(api_key=api_key, base_url=base_url)
        resp = await client.messages.create(
            model=model_id,
            system="Respond with just the word: ok",
            messages=[{"role": "user", "content": "Say ok"}],
            max_tokens=10,
        )
        text = ""
        for block in resp.content:
            if block.type == "text":
                text = block.text
                break
        return {"valid": True, "response": text}
    except Exception as e:
        raise HTTPException(422, f"Validation failed: {str(e)[:200]}")


@app.post("/api/models/add")
async def add_model(
    api_key: str = Form(...),
    base_url: str = Form(...),
    model_id: str = Form(...),
):
    """Validate and save a new model config."""
    # Validate first
    try:
        client = AsyncAnthropic(api_key=api_key, base_url=base_url)
        resp = await client.messages.create(
            model=model_id,
            system="Respond with just the word: ok",
            messages=[{"role": "user", "content": "Say ok"}],
            max_tokens=10,
        )
        text = ""
        for block in resp.content:
            if block.type == "text":
                text = block.text
                break
    except Exception as e:
        logger.warning("Model validation failed: model=%s error=%s", model_id, e)
        raise HTTPException(422, f"Validation failed: {str(e)[:200]}")

    model = {"id": model_id, "name": model_id, "api_key": api_key, "base_url": base_url}
    save_user_model(model)
    logger.info("Model added: id=%s base_url=%s", model_id, base_url)
    return {"valid": True, "response": text, "model": {k: v for k, v in model.items() if k != "api_key"}}


@app.delete("/api/models/{model_id}")
def delete_model(model_id: str):
    """Remove a user-added model."""
    remove_user_model(model_id)
    logger.info("Model deleted: id=%s", model_id)
    return {"deleted": model_id}


# ── Parse Route ────────────────────────────────────────────────────────

@app.post("/api/parse")
async def parse_resume(file: UploadFile = File(...)):
    """Upload a PDF/DOCX/LaTeX file and extract its text content."""
    ext = Path(file.filename).suffix.lower()
    if ext not in (".pdf", ".docx", ".tex"):
        raise HTTPException(400, f"Unsupported file type: {ext}")

    stem = Path(file.filename).stem
    saved_name = f"{stem}_{uuid.uuid4().hex[:8]}{ext}"
    dest = UPLOAD_DIR / saved_name
    with open(dest, "wb") as f:
        f.write(await file.read())

    try:
        if ext == ".pdf":
            text = parse_pdf(dest)
        elif ext == ".docx":
            text = parse_docx(dest)
        else:
            text = parse_latex(dest)
    except Exception as e:
        logger.error("Parse failed: file=%s ext=%s error=%s", file.filename, ext, e)
        raise HTTPException(422, f"Failed to parse file: {e}")

    return {"filename": file.filename, "saved_name": saved_name, "text": text, "type": ext.lstrip("."), "file_url": f"/api/files/{saved_name}"}


@app.get("/api/files/{filename}")
def serve_file(filename: str):
    """Serve an uploaded file (for PDF preview etc.)."""
    if ".." in filename or "/" in filename:
        logger.warning("File traversal attempt: %s", filename)
        raise HTTPException(400, "Invalid filename")
    fp = UPLOAD_DIR / filename
    if not fp.exists():
        logger.warning("File not found: %s", filename)
        raise HTTPException(404, "File not found")
    return FileResponse(str(fp))


# ── AI Analysis Routes ─────────────────────────────────────────────────

def _get_model_cfg_or_422(model_id: Optional[str] = None) -> dict:
    """Resolve model config from request param or default."""
    if model_id:
        cfg = get_model(model_id)
        if not cfg:
            raise HTTPException(422, f"Model '{model_id}' not found")
        return cfg
    models = load_models()
    if not models:
        raise HTTPException(503, "No AI models configured")
    return models[0]  # default


@app.post("/api/analyze")
async def analyze_gaps(resume_text: str = Form(...), jd_text: str = Form(...), model_id: str = Form("")):
    cfg = _get_model_cfg_or_422(model_id or None)
    prompt = f"""Analyze the gap between this resume and the job description.

RESUME:
{resume_text}

JOB DESCRIPTION:
{jd_text}

Provide a structured analysis:
1. **Strong matches** (keywords/experience that directly align)
2. **Repackagable** (experience that can be positioned to fit)
3. **Genuine gaps** (missing skills/experience)
4. **Keywords to add** (specific JD keywords not in resume)
5. **Overall fit score** (1-10) with brief rationale"""

    result, thinking, truncated = await _call_claude(cfg, SYSTEM_PROMPT, [{"role": "user", "content": prompt}], max_tokens=8192)
    return {"analysis": result, "thinking": thinking, "truncated": truncated}


@app.post("/api/assess")
async def assess_resume(resume_text: str = Form(...), jd_text: str = Form(...), model_id: str = Form("")):
    cfg = _get_model_cfg_or_422(model_id or None)
    prompt = f"""Evaluate this resume's effectiveness for getting an interview.

RESUME:
{resume_text}

JOB DESCRIPTION:
{jd_text}

Score each dimension 1-10 with brief reasoning:
1. **ATS keyword match**
2. **First impression** (15-second scan)
3. **Narrative coherence** (story consistency)
4. **Impact evidence** (quantified results)
5. **Overall interview chance**

Then provide:
- Top 3 strengths
- Top 3 weaknesses
- One-paragraph summary of what a recruiter would think"""

    result, thinking, truncated = await _call_claude(cfg, SYSTEM_PROMPT, [{"role": "user", "content": prompt}], max_tokens=8192)
    return {"assessment": result, "thinking": thinking, "truncated": truncated}


@app.post("/api/remediate")
async def remediate_gaps(resume_text: str = Form(...), jd_text: str = Form(...), model_id: str = Form("")):
    cfg = _get_model_cfg_or_422(model_id or None)
    prompt = f"""Create a concrete remediation plan for the gaps between this resume and job description.

RESUME:
{resume_text}

JOB DESCRIPTION:
{jd_text}

For each genuine gap (not repackagable), provide:
1. **Gap** - what's missing
2. **Priority** - High/Medium/Low
3. **Learning resource** - specific tutorial, course, or project idea
4. **Time estimate** - hours needed
5. **How to demonstrate** - how to show this skill on the resume after learning

Group into: Week 1 (urgent), Week 2-4, Month 2+"""

    result, thinking, truncated = await _call_claude(cfg, SYSTEM_PROMPT, [{"role": "user", "content": prompt}], max_tokens=8192)
    return {"plan": result, "thinking": thinking, "truncated": truncated}


@app.post("/api/rewrite")
async def rewrite_resume(
    resume_text: str = Form(...),
    jd_text: str = Form(...),
    section: str = Form("all"),
    instruction: str = Form(""),
    model_id: str = Form(""),
):
    cfg = _get_model_cfg_or_422(model_id or None)
    prompt = f"""Rewrite the resume to be more compelling, following storytelling logic:
- Project Background: what was the context
- Problem: what pain point existed
- Solution: what you designed and built
- Impact: quantified results and user value

RESUME:
{resume_text}

JOB DESCRIPTION:
{jd_text}

Section to focus on: {section}
Additional instructions: {instruction}

Rules:
- Keep all factual claims truthful
- Chinese narrative with embedded English tech keywords (do NOT translate keywords like Tool Calling, Permission Gate, etc.)
- Each bullet should tell a mini-story
- Prioritize impact and results over descriptions
- Output the complete rewritten resume in the original format (Chinese text body + English keywords)"""

    result, thinking, truncated = await _call_claude(cfg, SYSTEM_PROMPT, [{"role": "user", "content": prompt}], max_tokens=16384)
    return {"rewritten": result, "thinking": thinking, "truncated": truncated}


# ── Streaming ──────────────────────────────────────────────────────────

ANALYSIS_PROMPTS = {
    "analysis": """Analyze the gap between this resume and the job description.

RESUME:
{resume_text}

JOB DESCRIPTION:
{jd_text}

Provide a structured analysis:
1. **Strong matches** (keywords/experience that directly align)
2. **Repackagable** (experience that can be positioned to fit)
3. **Genuine gaps** (missing skills/experience)
4. **Keywords to add** (specific JD keywords not in resume)
5. **Overall fit score** (1-10) with brief rationale""",
    "assessment": """Evaluate this resume's effectiveness for getting an interview.

RESUME:
{resume_text}

JOB DESCRIPTION:
{jd_text}

Score each dimension 1-10 with brief reasoning:
1. **ATS keyword match**
2. **First impression** (15-second scan)
3. **Narrative coherence** (story consistency)
4. **Impact evidence** (quantified results)
5. **Overall interview chance**

Then provide:
- Top 3 strengths
- Top 3 weaknesses
- One-paragraph summary of what a recruiter would think""",
    "remediation": """Create a concrete remediation plan for the gaps between this resume and job description.

RESUME:
{resume_text}

JOB DESCRIPTION:
{jd_text}

For each genuine gap (not repackagable), provide:
1. **Gap** - what's missing
2. **Priority** - High/Medium/Low
3. **Learning resource** - specific tutorial, course, or project idea
4. **Time estimate** - hours needed
5. **How to demonstrate** - how to show this skill on the resume after learning

Group into: Week 1 (urgent), Week 2-4, Month 2+""",
    "rewrite": """Rewrite the resume to be more compelling, following storytelling logic:
- Project Background: what was the context
- Problem: what pain point existed
- Solution: what you designed and built
- Impact: quantified results and user value

RESUME:
{resume_text}

JOB DESCRIPTION:
{jd_text}

Section to focus on: {section}
Additional instructions: {instruction}

Rules:
- Keep all factual claims truthful
- Chinese narrative with embedded English tech keywords (do NOT translate keywords like Tool Calling, Permission Gate, etc.)
- Each bullet should tell a mini-story
- Prioritize impact and results over descriptions
- Output the complete rewritten resume in the original format (Chinese text body + English keywords)""",
}


@app.post("/api/stream")
async def stream_analysis(
    type: str = Form(...),
    resume_text: str = Form(...),
    jd_text: str = Form(...),
    section: str = Form("all"),
    instruction: str = Form(""),
    model_id: str = Form(""),
):
    """Stream AI analysis as NDJSON events. Used for progressive rendering."""
    cfg = _get_model_cfg_or_422(model_id or None)
    if type not in ANALYSIS_PROMPTS:
        raise HTTPException(400, f"Unknown analysis type: {type}")

    prompt = ANALYSIS_PROMPTS[type].format(
        resume_text=resume_text, jd_text=jd_text, section=section, instruction=instruction,
    )
    max_tokens = 16384 if type == "rewrite" else 8192

    async def event_stream():
        client = AsyncAnthropic(
            api_key=cfg["api_key"],
            base_url=cfg.get("base_url", "https://api.anthropic.com"),
        )
        try:
            stream = await client.messages.create(
                model=cfg["id"],
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                stream=True,
            )
            text = ""
            thinking = ""
            async for event in stream:
                if event.type == "content_block_delta":
                    d = event.delta
                    if hasattr(d, "text") and d.text:
                        text += d.text
                        yield json.dumps({"text": text, "thinking": thinking, "done": False}) + "\n"
                    elif hasattr(d, "thinking") and d.thinking:
                        thinking += d.thinking
                        yield json.dumps({"text": text, "thinking": thinking, "done": False}) + "\n"
                elif event.type == "message_delta":
                    truncated = getattr(event.delta, "stop_reason", None) == "max_tokens"
                    yield json.dumps({"text": text, "thinking": thinking, "done": True, "truncated": truncated}) + "\n"
        except Exception as e:
            logger.error("Stream failed: model=%s error=%s", cfg["id"], str(e)[:200])
            yield json.dumps({"error": str(e)[:200]}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


# ── LaTeX Compilation ──────────────────────────────────────────────────

@app.post("/api/compile")
async def compile_latex(latex: str = Form(...)):
    """Compile LaTeX to PDF using tectonic."""
    srcdir = UPLOAD_DIR / "latex-src"
    srcdir.mkdir(parents=True, exist_ok=True)

    tex_file = srcdir / "main.tex"
    tex_file.write_text(latex, encoding="utf-8")

    try:
        result = subprocess.run(
            ["tectonic", str(tex_file)],
            cwd=srcdir,
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
            env={**os.environ, "TECTONIC_CACHE_DIR": str(CACHE_DIR)},
        )
        logger.info("LaTeX compiled ok (%d bytes src)", len(latex))
    except subprocess.CalledProcessError as e:
        logger.error("LaTeX compile failed: stderr=%s", e.stderr[:500])
        raise HTTPException(422, f"LaTeX compilation failed:\n{e.stderr[:2000]}")
    except FileNotFoundError:
        logger.error("tectonic binary not found")
        raise HTTPException(500, "tectonic not found; install it with: brew install tectonic")

    pdf_path = srcdir / "main.pdf"
    if not pdf_path.exists():
        logger.error("Compilation produced no PDF: %s", srcdir)
        raise HTTPException(422, "Compilation produced no PDF")

    sz = pdf_path.stat().st_size
    logger.info("PDF served: size=%d bytes", sz)
    return FileResponse(str(pdf_path), media_type="application/pdf",
                       headers={"Content-Disposition": "inline; filename=resume.pdf"})


def _is_cache_warm() -> bool:
    """Check if tectonic cache already has compiled format (indicates packages cached)."""
    return any(CACHE_DIR.glob("formats/*.fmt"))


def _prewarm_tectonic():
    """Pre-warm tectonic cache in background thread (non-blocking)."""
    if _is_cache_warm():
        logger.info("Tectonic cache already warm at %s", CACHE_DIR)
        return
    warm_dir = UPLOAD_DIR / "latex-src"
    warm_dir.mkdir(parents=True, exist_ok=True)
    warm_tex = warm_dir / "warmup.tex"
    warm_tex.write_text(
        "\\documentclass{article}\\usepackage[UTF8,fontset=fandol]{ctex}\\begin{document}warmup\\end{document}",
        encoding="utf-8",
    )

    import threading

    def _warm():
        logger.info("Pre-warming tectonic cache (background)...")
        try:
            subprocess.run(
                ["tectonic", str(warm_tex)],
                cwd=warm_dir,
                capture_output=True,
                text=True,
                timeout=300,
                check=True,
                env={**os.environ, "TECTONIC_CACHE_DIR": str(CACHE_DIR)},
            )
            logger.info("Tectonic cache pre-warmed at %s", CACHE_DIR)
        except Exception as e:
            logger.warning("Tectonic pre-warm failed (will warm on first request): %s", e)

    threading.Thread(target=_warm, daemon=True).start()


if __name__ == "__main__":
    import uvicorn
    models = load_models()
    logger.info("=" * 50)
    logger.info("Resume AI Editor backend starting")
    logger.info("Log file: %s", log_file)
    logger.info("Models available: %d (%s)", len(models), ", ".join(m["id"] for m in models))
    logger.info("Tectonic cache: %s", CACHE_DIR)
    logger.info("Listening on http://0.0.0.0:8000")
    logger.info("=" * 50)
    _prewarm_tectonic()
    logger.info("Ready")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, workers=2,
                log_config=None)
