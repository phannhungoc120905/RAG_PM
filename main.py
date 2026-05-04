import os
import json
import uuid
import socket
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
import mysql.connector
from mysql.connector import pooling
from pypdf import PdfReader
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains import create_retrieval_chain

# Load .env from workspace root first, then fallback to local folder.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_ENV_PATH = os.path.join(os.path.dirname(BASE_DIR), ".env")
LOCAL_ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(
    ROOT_ENV_PATH if os.path.exists(ROOT_ENV_PATH) else LOCAL_ENV_PATH,
    override=True,
)

app = FastAPI()

MODEL_NAME = "llama3.2"
HISTORY_FILE = "history.json"
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "local_rag_pm")

db_pool = None


def init_db_pool():
    global db_pool
    if db_pool is not None:
        return
    db_pool = pooling.MySQLConnectionPool(
        pool_name="rag_pm_pool",
        pool_size=5,
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=False,
    )


def get_db_connection():
    if db_pool is None:
        init_db_pool()
    return db_pool.get_connection()


def get_history_from_file():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []

def get_history():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                d.title AS filename,
                s.summary_content AS summary,
                DATE_FORMAT(s.created_at, '%Y-%m-%d %H:%i:%s') AS timestamp
            FROM summaries s
            JOIN documents d ON d.id = s.document_id
            ORDER BY s.created_at DESC
            LIMIT 20
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception:
        return get_history_from_file()


def save_to_history_file(filename, summary):
    history = get_history_from_file()
    history.insert(0, {
        "filename": filename,
        "summary": summary,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    history = history[:20]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def save_to_history(filename, summary):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        document_id = str(uuid.uuid4())
        summary_id = str(uuid.uuid4())
        file_extension = os.path.splitext(filename)[1].replace(".", "").lower()[:10]

        cursor.execute(
            """
            INSERT INTO documents (
                id, title, storage_path, file_extension, status, created_at
            ) VALUES (%s, %s, %s, %s, %s, NOW())
            """,
            (
                document_id,
                filename,
                f"uploads/{filename}",
                file_extension,
                "indexed",
            ),
        )

        cursor.execute(
            """
            INSERT INTO summaries (
                id, document_id, model_name, summary_content, word_count,
                execution_time_ms, groundedness_score, status, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                summary_id,
                document_id,
                MODEL_NAME,
                summary,
                len(summary.split()),
                0,
                None,
                "final",
            ),
        )

        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        save_to_history_file(filename, summary)


@app.on_event("startup")
async def startup_event():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(buffered=True)
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        print(f"[DB] Connected to MySQL {DB_HOST}:{DB_PORT}/{DB_NAME}")
    except Exception as e:
        print(f"[DB] Connection failed, fallback to JSON history: {e}")


def resolve_available_port(preferred_port: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", preferred_port)) != 0:
            return preferred_port
    return preferred_port + 1

def extract_text(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        if page.extract_text():
            text += page.extract_text()
    return text

def summarize_with_ollama(text):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = text_splitter.create_documents([text])
    embeddings = OllamaEmbeddings(model=MODEL_NAME)
    vectorstore = FAISS.from_documents(chunks, embeddings)
    llm = OllamaLLM(model=MODEL_NAME)
    prompt = ChatPromptTemplate.from_template("""
    Bạn là một trợ lý tóm tắt văn bản chuyên nghiệp. 
    Hãy tóm tắt nội dung sau đây thành 5 ý chính quan trọng nhất dưới dạng danh sách bullet bằng tiếng Việt.
    Nội dung: {context}
    Tóm tắt:""")
    document_chain = create_stuff_documents_chain(llm, prompt)
    retriever = vectorstore.as_retriever()
    retrieval_chain = create_retrieval_chain(retriever, document_chain)
    response = retrieval_chain.invoke({"input": "Hãy tóm tắt văn bản này"})
    return response["answer"]

@app.get("/", response_class=HTMLResponse)
async def root():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Local RAG Summarizer (Ollama) is running!</h1>"

@app.get("/history")
async def history():
    return get_history()

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        temp_path = f"temp_{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(contents)
        
        text = extract_text(temp_path)
        summary = summarize_with_ollama(text)
        
        # Save to history
        save_to_history(file.filename, summary)

        if os.path.exists(temp_path):
            os.remove(temp_path)
        return {"summary": summary}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    import sys
    port = 8000
    if "--port" in sys.argv:
        try:
            port = int(sys.argv[sys.argv.index("--port") + 1])
        except (ValueError, IndexError):
            pass
    run_port = resolve_available_port(port)
    if run_port != port:
        print(f"[Server] Port {port} is busy, using {run_port} instead")
    uvicorn.run(app, host="0.0.0.0", port=run_port)