from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import psycopg2
import json

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