import os
import ast
import io
import json
import uuid
import requests
from datetime import datetime
from contextlib import contextmanager
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

os.environ["CUDA_VISIBLE_DEVICES"] = ""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import psycopg2
from psycopg2 import pool
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote

app = FastAPI(title="prosjekt-oyenstikker", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

model = SentenceTransformer('all-MiniLM-L6-v2')

db_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    host=os.getenv("POSTGRES_HOST", "localhost"),
    database=os.getenv("POSTGRES_DB", "memory"),
    user=os.getenv("POSTGRES_USER", "postgres"),
    password=os.getenv("POSTGRES_PASSWORD", "postgres")
)

@contextmanager
def get_conn():
    conn = db_pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        db_pool.putconn(conn)

SESSIONS_DIR = os.getenv("SESSIONS_DIR", "./sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

MODEL_PARAMS = {
    "phi3:mini":   {"short": {"temperature": 0.1, "num_predict": 150}, "long": {"temperature": 0.4, "num_predict": 400}},
    "mistral":     {"short": {"temperature": 0.2, "num_predict": 200}, "long": {"temperature": 0.5, "num_predict": 500}},
    "llama3.1:8b": {"short": {"temperature": 0.2, "num_predict": 250}, "long": {"temperature": 0.6, "num_predict": 600}},
    "phi4-mini":   {"short": {"temperature": 0.2, "num_predict": 200}, "long": {"temperature": 0.5, "num_predict": 500}},
}

DEFAULT_PARAMS = {
    "short": {"temperature": 0.2, "num_predict": 200},
    "long":  {"temperature": 0.5, "num_predict": 500}
}

CONVERSATION_TRIGGERS = [
    "we ", "this chat", "just talked", "just covered", "we covered",
    "we discussed", "we talked", "this conversation", "so far",
    "what did we", "what have we", "topics we", "in this session",
    "earlier you", "you said", "you mentioned", "i said", "i asked"
]

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://duckduckgo.com/",
    "DNT": "1",
}

def is_conversation_question(q: str) -> bool:
    return any(trigger in q.lower() for trigger in CONVERSATION_TRIGGERS)

class Document(BaseModel):
    content: str
    metadata: dict = {}

class ChatMessage(BaseModel):
    role: str
    content: str

class Question(BaseModel):
    q: str
    model: str = "phi3:mini"
    length: str = "short"
    session_id: Optional[str] = None
    history: Optional[List[ChatMessage]] = []

class SessionCreate(BaseModel):
    name: Optional[str] = None

class WebQuery(BaseModel):
    q: str
    max_results: int = 5

class FetchRequest(BaseModel):
    url: str
    max_chars: int = 8000

def load_session(session_id: str):
    path = f"{SESSIONS_DIR}/{session_id}.json"
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None

def save_session(session_id: str, data: dict):
    path = f"{SESSIONS_DIR}/{session_id}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

@app.get("/health")
def health():
    return {"status": "ok", "version": "0.4.0"}

@app.post("/session/new")
def new_session(req: SessionCreate):
    session_id = str(uuid.uuid4())[:8]
    name = req.name or f"session-{datetime.now().strftime('%Y%m%d-%H%M')}"
    data = {
        "id": session_id,
        "name": name,
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
        "history": []
    }
    save_session(session_id, data)
    return {"session_id": session_id, "name": name}

@app.get("/session/list")
def list_sessions():
    sessions = []
    for fname in sorted(os.listdir(SESSIONS_DIR), reverse=True):
        if fname.endswith(".json"):
            try:
                with open(f"{SESSIONS_DIR}/{fname}") as f:
                    s = json.load(f)
                sessions.append({
                    "id": s["id"],
                    "name": s["name"],
                    "created": s["created"],
                    "updated": s["updated"],
                    "message_count": len(s["history"])
                })
            except Exception:
                continue
    return sessions

@app.get("/session/{session_id}")
def get_session(session_id: str):
    data = load_session(session_id)
    if not data:
        return {"error": "session not found"}
    return data

@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    path = f"{SESSIONS_DIR}/{session_id}.json"
    if os.path.exists(path):
        os.remove(path)
        return {"status": "deleted"}
    return {"error": "session not found"}

@app.post("/ingest")
def ingest(doc: Document):
    embedding = model.encode(doc.content).tolist()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO documents (content, embedding, metadata) VALUES (%s, %s::vector, %s)",
            (doc.content, str(embedding), json.dumps(doc.metadata))
        )
    return {"status": "ok", "chars": len(doc.content)}

@app.get("/search")
def search(q: str, k: int = 5):
    embedding = model.encode(q).tolist()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, content, metadata FROM documents ORDER BY embedding <-> %s::vector LIMIT %s",
            (str(embedding), min(k, 20))
        )
        results = cur.fetchall()
    return [{"id": r[0], "content": r[1], "metadata": r[2]} for r in results]

@app.post("/ask")
def ask(question: Question):
    params = MODEL_PARAMS.get(question.model, DEFAULT_PARAMS).get(
        question.length, DEFAULT_PARAMS["short"]
    )
    length_instruction = (
        "Be concise. Answer in 1-3 sentences maximum."
        if question.length == "short"
        else "Be thorough. Explain your reasoning and cite specific details."
    )
    conv_mode = is_conversation_question(question.q)
    history_text = ""
    if question.history:
        recent = question.history[-12:] if conv_mode else question.history[-6:]
        history_text = "\nRecent conversation:\n"
        for msg in recent:
            prefix = "User" if msg.role == "user" else "Oyenstikker"
            history_text += f"{prefix}: {msg.content}\n"

    if conv_mode:
        context_chunks = []
        prompt = (
            "Respond in plain text only. No HTML, no markdown, no code blocks.\n\n"
            "You are Oyenstikker. Answer using ONLY the conversation history below. "
            "Do not use outside knowledge.\n\n"
            f"{length_instruction}\n"
            f"{history_text}\n"
            f"Question: {question.q}\n"
            "Answer:"
        )
    else:
        embedding = model.encode(question.q).tolist()
        with get_conn() as conn:
            cur = conn.cursor()
            if question.session_id:
                cur.execute(
                    """
                    (SELECT content, metadata, embedding <-> %s::vector AS dist
                     FROM documents WHERE metadata->>'session_id' = %s
                     ORDER BY dist LIMIT 3)
                    UNION ALL
                    (SELECT content, metadata, embedding <-> %s::vector AS dist
                     FROM documents WHERE metadata->>'session_id' != %s
                        OR metadata->>'session_id' IS NULL
                     ORDER BY dist LIMIT 2)
                    ORDER BY dist LIMIT 5
                    """,
                    (str(embedding), question.session_id,
                     str(embedding), question.session_id)
                )
            else:
                cur.execute(
                    "SELECT content, metadata, embedding <-> %s::vector AS dist "
                    "FROM documents ORDER BY dist LIMIT 5",
                    (str(embedding),)
                )
            results = cur.fetchall()
        context_chunks = [r[0] for r in results]
        context = "\n---\n".join(context_chunks)
        prompt = (
            "Respond in plain text only. No HTML, no markdown, no code blocks.\n\n"
            "You are Oyenstikker, a research assistant with access to a personal knowledge base. "
            "Answer ONLY using the context and conversation history below. "
            "Do not use outside knowledge. "
            "If the context is not relevant, say so and explain what data would need to be ingested.\n\n"
            f"{length_instruction}\n\n"
            f"Knowledge base context:\n{context}\n"
            f"{history_text}\n"
            f"Question: {question.q}\n"
            "Answer:"
        )

    try:
        response = requests.post(
            os.getenv("OLLAMA_HOST", "http://localhost:11434") + "/api/generate",
            json={
                "model": question.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": params["temperature"],
                    "num_predict": params["num_predict"]
                }
            },
            timeout=120
        )
        response.raise_for_status()
        answer = response.json()["response"]
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Ollama unreachable: {e}")

    if question.session_id:
        session = load_session(question.session_id)
        if session:
            session["history"].append({"role": "user", "content": question.q, "timestamp": datetime.now().isoformat()})
            session["history"].append({"role": "assistant", "content": answer, "timestamp": datetime.now().isoformat()})
            session["updated"] = datetime.now().isoformat()
            save_session(question.session_id, session)

    return {
        "answer": answer,
        "context_used": context_chunks,
        "session_id": question.session_id,
        "mode": "conversation" if conv_mode else "knowledge"
    }

@app.get("/graph")
def graph():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, content, metadata, embedding::text FROM documents")
        rows = cur.fetchall()
    nodes = []
    for row in rows:
        try:
            vec = ast.literal_eval(row[3])
        except Exception:
            continue
        nodes.append({
            "id": row[0],
            "content": row[1][:200],
            "metadata": row[2] or {},
            "embedding": vec,
        })
    return {"nodes": nodes, "count": len(nodes)}

@app.post("/websearch")
def websearch(query: WebQuery):
    try:
        res = requests.get(
            "https://html.duckduckgo.com/html/",
            headers=BROWSER_HEADERS,
            params={"q": query.q, "kl": "us-en"},
            timeout=10
        )
        soup = BeautifulSoup(res.text, "html.parser")
        results = []
        for r in soup.select(".result"):
            title_el = r.select_one(".result__a")
            body_el = r.select_one(".result__snippet")
            if title_el and body_el:
                href = title_el.get("href", "")
                # DDG returns protocol-relative redirect URLs like //duckduckgo.com/l/?uddg=...
                if "/l/" in href and "uddg=" in href:
                    try:
                        qs = parse_qs(urlparse(href).query)
                        href = unquote(qs.get("uddg", [href])[0])
                    except Exception:
                        pass
                results.append({
                    "title": title_el.get_text(strip=True),
                    "href": href,
                    "body": body_el.get_text(strip=True)
                })
            if len(results) >= query.max_results:
                break
        return {"results": results, "query": query.q}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {e}")

@app.post("/fetch")
def fetch_url(req: FetchRequest):
    try:
        res = requests.get(req.url, headers=BROWSER_HEADERS, timeout=15)
        content_type = res.headers.get("content-type", "")

        if "pdf" in content_type or req.url.lower().endswith(".pdf"):
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(res.content))
                text = "\n".join(p.extract_text() for p in reader.pages if p.extract_text())
                return {"text": text[:req.max_chars], "type": "pdf", "url": req.url}
            except Exception as e:
                raise HTTPException(status_code=422, detail=f"PDF parse failed: {e}")

        soup = BeautifulSoup(res.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [l for l in text.splitlines() if l.strip()]
        clean = "\n".join(lines)
        return {"text": clean[:req.max_chars], "type": "html", "url": req.url}

    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Fetch failed: {e}")