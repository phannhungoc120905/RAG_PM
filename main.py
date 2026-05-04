import os
import json
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from ocr.router import router as ocr_router

app = FastAPI()
app.include_router(ocr_router)

MODEL_NAME = "llama3.2"
HISTORY_FILE = "history.json"


def get_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return []


def save_to_history(filename, summary):
    history = get_history()
    history.insert(
        0,
        {
            "filename": filename,
            "summary": summary,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    history = history[:20]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


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
    prompt = ChatPromptTemplate.from_template(
        """
    Bạn là một trợ lý tóm tắt văn bản chuyên nghiệp. 
    Hãy tóm tắt nội dung sau đây thành 5 ý chính quan trọng nhất dưới dạng danh sách bullet bằng tiếng Việt.
    Nội dung: {context}
    Tóm tắt:"""
    )
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

        save_to_history(file.filename, summary)

        if os.path.exists(temp_path):
            os.remove(temp_path)
        return {"summary": summary}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import sys
    import uvicorn

    port = 8000
    if "--port" in sys.argv:
        try:
            port = int(sys.argv[sys.argv.index("--port") + 1])
        except (ValueError, IndexError):
            pass
    uvicorn.run(app, host="0.0.0.0", port=port)
