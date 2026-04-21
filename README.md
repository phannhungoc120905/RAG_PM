# AI PDF Summarizer (Local RAG)

Ứng dụng tóm tắt file PDF sử dụng công nghệ RAG (Retrieval-Augmented Generation) chạy hoàn toàn offline với mô hình Llama 3.2 thông qua Ollama.

## 🌟 Tính năng
- **Tóm tắt PDF thông minh**: Trích xuất và tóm tắt 5 ý chính quan trọng nhất.
- **Chạy Offline**: Bảo mật dữ liệu, không tốn phí bản quyền OpenAI.
- **Giao diện Web hiện đại**: Hỗ trợ kéo thả file, hiệu ứng loading mượt mà.
- **Lưu lịch sử**: Tự động lưu lại các bản tóm tắt cũ để xem lại nhanh chóng.

## 🛠 Công nghệ sử dụng
- **Backend**: FastAPI (Python)
- **AI Orchestration**: LangChain
- **Vector Database**: FAISS
- **Local LLM**: Ollama (Model: `llama3.2`)
- **Frontend**: HTML5, Tailwind CSS

## 📋 Yêu cầu hệ thống
1. Đã cài đặt [Python 3.9+](https://www.python.org/).
2. Đã cài đặt [Ollama](https://ollama.com/) và tải model llama3.2:
   ```bash
   ollama pull llama3.2
   ```

## 🚀 Hướng dẫn cài đặt

1. **Clone repository:**
   ```bash
   git clone https://github.com/phannhungoc120905/RAG_PM.git
   cd RAG_PM
   ```

2. **Cài đặt thư viện:**
   ```bash
   pip install fastapi uvicorn pypdf langchain-ollama langchain-community faiss-cpu python-multipart python-dotenv
   ```

3. **Chạy ứng dụng:**
   ```bash
   python main.py --port 8002
   ```

4. **Truy cập:**
   Mở trình duyệt và vào địa chỉ [http://localhost:8002](http://localhost:8002)

## 📁 Cấu trúc thư mục
- `main.py`: Mã nguồn Backend xử lý RAG và API.
- `index.html`: Giao diện người dùng.
- `history.json`: Lưu trữ lịch sử tóm tắt (tự sinh).
- `.gitignore`: Cấu hình bỏ qua các file không cần thiết khi đẩy lên Git.

---
Phát triển bởi [phannhungoc120905](https://github.com/phannhungoc120905)