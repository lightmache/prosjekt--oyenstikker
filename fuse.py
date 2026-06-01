from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import psycopg2
import json
import requests

app = FastAPI()
model = SentenceTransformer('all-MiniLM-L6-v2')

conn = psycopg2.connect(
    host="localhost",
    database="memory",
    user="postgres",
    password="postgres"
)

class Document(BaseModel):
    content: str
    metadata: dict = {}

class Question(BaseModel):
    q: str
    model: str = "llama3.1:8b"

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
    embedding = model.encode(question.q).tolist()
    cur = conn.cursor()
    cur.execute(
        "SELECT content FROM documents ORDER BY embedding <-> %s LIMIT 3",
        (str(embedding),)
    )
    results = cur.fetchall()
    context = "\n".join([r[0] for r in results])
    prompt = f"""You are a helpful assistant. Use the following context from the user's personal knowledge base to answer their question. If the context is not relevant, say so.

Context:
{context}

Question: {question.q}

Answer:"""
    response = requests.post("http://localhost:11434/api/generate", json={
        "model": question.model,
        "prompt": prompt,
        "stream": False
    })
    return {
        "answer": response.json()["response"],
        "context_used": [r[0] for r in results]
    }