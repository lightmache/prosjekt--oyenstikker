import logging
logging.basicConfig(
    filename="logs/oyenstikker.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("oyenstikker")

import os
import json
import uuid
import requests
import psycopg2

from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

load_dotenv()
os.environ["CUDA_VISIBLE_DEVICES"] = ""

app = FastAPI()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

model = SentenceTransformer('all-MiniLM-L6-v2')

conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST", "localhost"),
    database=os.getenv("POSTGRES_DB", "memory"),
    user=os.getenv("POSTGRES_USER", "postgres"),
    password=os.getenv("POSTGRES_PASSWORD", "postgres")
)

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

def is_conversation_question(q: str) -> bool:
    q_lower = q.lower()
    return any(trigger in q_lower for trigger in CONVERSATION_TRIGGERS)

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
            with open(f"{SESSIONS_DIR}/{fname}") as f:
                s = json.load(f)
                sessions.append({
                    "id": s["id"],
                    "name": s["name"],
                    "created": s["created"],
                    "updated": s["updated"],
                    "message_count": len(s["history"])
                })
    return sessions

@app.get("/session/{session_id}")
def get_session(session_id: str):
    data = load_session(session_id)
    if not data:
        return {"error": "session not found"}
    return data

@app.post("/ingest")
def ingest(doc: Document):
    embedding = model.encode(doc.content).tolist()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO documents (content, embedding, metadata) VALUES (%s, %s, %s)",
        (doc.content, str(embedding), json.dumps(doc.metadata))
    )
    conn.commit()
    return {"status": "ok"}

@app.get("/search")
def search(q: str, k: int = 5):
    embedding = model.encode(q).tolist()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, content, metadata FROM documents ORDER BY embedding <-> %s LIMIT %s",
        (str(embedding), k)
    )
    results = cur.fetchall()
    return [{"id": r[0], "content": r[1], "metadata": r[2]} for r in results]

@app.post("/ask")
def ask(question: Question):
    params = MODEL_PARAMS.get(question.model, DEFAULT_PARAMS).get(question.length, DEFAULT_PARAMS["short"])

    if question.length == "short":
        length_instruction = "Be concise. Answer in 1-3 sentences maximum."
    else:
        length_instruction = "Be thorough. Explain your reasoning and cite specific details."

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
            "You are Oyenstikker. Answer the question using ONLY the conversation history below. "
            "Do not use any outside knowledge.\n\n"
            f"{length_instruction}\n"
            f"{history_text}\n"
            f"Question: {question.q}\n"
            "Answer:"
        )
    else:
        embedding = model.encode(question.q).tolist()
        cur = conn.cursor()
        cur.execute(
            "SELECT content FROM documents ORDER BY embedding <-> %s LIMIT 3",
            (str(embedding),)
        )
        results = cur.fetchall()
        context_chunks = [r[0] for r in results]
        context = "\n".join(context_chunks)

        prompt = (
            "Respond in plain text only. No HTML, no markdown, no code blocks.\n\n"
            "You are Oyenstikker, a research assistant with access to a personal knowledge base. "
            "Answer ONLY using the context provided below and the recent conversation history. "
            "Do not use outside knowledge. If the context contains relevant information, use it to answer directly. "
            "If you cannot answer from the context, explain specifically what type of data would need to be ingested.\n\n"
            f"{length_instruction}\n\n"
            f"Knowledge base context:\n{context}\n"
            f"{history_text}\n"
            f"Question: {question.q}\n"
            "Answer:"
        )

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
        }
    )

    answer = response.json()["response"]

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

class WebQuery(BaseModel):
    q: str
    max_results: int = 5

@app.post("/websearch")
def websearch(query: WebQuery):
    import requests as req
    from bs4 import BeautifulSoup
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
    }
    url = f"https://html.duckduckgo.com/html/?q={query.q}"
    res = req.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(res.text, "html.parser")
    results = []
    for r in soup.select(".web-result")[:query.max_results]:
        title_el = r.select_one(".result__a")
        snippet_el = r.select_one(".result__snippet")
        if title_el:
            from urllib.parse import urlparse, parse_qs, unquote
            href = title_el.get("href", "")
            if "/l/" in href and "uddg=" in href:
                try:
                    qs = parse_qs(urlparse(href).query)
                    href = unquote(qs.get("uddg", [href])[0])
                except Exception:
                    pass
            results.append({
                "title": title_el.get_text(strip=True),
                "url": href,
                "snippet": snippet_el.get_text(strip=True) if snippet_el else ""
            })
    return {"results": results}

