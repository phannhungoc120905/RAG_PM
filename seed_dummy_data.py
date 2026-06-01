"""
Script tạo dữ liệu ảo vào database để demo hệ thống.
Chạy: python seed_dummy_data.py
"""
from datetime import datetime, date, timedelta
import json
from sqlalchemy.orm import Session
from db.database import SessionLocal, engine, Base
from db.models import Document, ChunkMetadata, SummaryHistory, User
from config import settings

# Tạo tables nếu chưa tồn tại
Base.metadata.create_all(bind=engine)

DUMMY_DOCUMENTS = [
    {
        "filename": "quyetdinh_2024_001.pdf",
        "original_filename": "Quyết định số 001/2024 về tổ chức hoạt động.pdf",
        "document_type": "quyet_dinh",
        "document_number": "001/2024/QĐ-UBND",
        "document_title": "Quyết định số 001/2024 của UBND về tổ chức hoạt động quản lý tài nguyên nước",
        "document_summary": """
        🎯 TÓNG DÀI: Quyết định nhằm thành lập ban quản lý tài nguyên nước toàn quốc, giao trách nhiệm cho các đơn vị chuyên trách.

        📋 ĐIỂM CHÍNH:
        • Thành lập Ban Quản lý Tài nguyên Nước trực thuộc Bộ Tài nguyên
        • Giao trách nhiệm giám sát chất lượng nước toàn quốc
        • Xây dựng quy định khai thác nước ngầm bền vững
        • Tổ chức đào tạo, nâng cao kỹ năng cho 5000 cán bộ

        📌 CHI TIẾT QUAN TRỌNG:
        • Mã QĐ: 001/2024/QĐ-UBND
        • Ngày ban hành: 15/01/2024
        • Cơ quan ban hành: UBND Thành phố Hà Nội
        • Hiệu lực: 01/02/2024
        • Điều 5: Cấp phát 50 tỷ VND cho hoạt động giám sát

        ✅ KẾT LUẬN: Ban phải báo cáo tiến độ hàng quý, đề xuất cải tiến hàng năm.
        """,
        "issuer_name": "UBND Thành phố Hà Nội",
        "issued_date": date(2024, 1, 15),
        "effective_date": date(2024, 2, 1),
        "page_count": 12,
        "mime_type": "application/pdf",
    },
    {
        "filename": "congvan_2024_05.docx",
        "original_filename": "Công văn số 05/2024 hướng dẫn thực hiện.docx",
        "document_type": "cong_van",
        "document_number": "05/2024/CV-BGD",
        "document_title": "Công văn số 05/2024 của Bộ GD&ĐT hướng dẫn thực hiện chương trình học mới",
        "document_summary": """
        🎯 TÓNG DÀI: Bộ GD&ĐT hướng dẫn các trường thực hiện chương trình giáo dục phổ thông mới năm 2024-2025.

        📋 ĐIỂM CHÍNH:
        • Áp dụng chương trình học thí điểm từ lớp 1, 6, 10
        • Tổ chức đào tạo giáo viên trước ngày 01/09/2024
        • Chuẩn bị tài liệu, sách giáo khoa trước 01/08/2024
        • Thiết lập nhóm tư vấn chuyên môn ở mỗi tỉnh

        📌 CHI TIẾT QUAN TRỌNG:
        • Mã CV: 05/2024/CV-BGD
        • Ngày phát hành: 25/05/2024
        • Cơ quan phát hành: Bộ Giáo dục và Đào tạo
        • Bắt buộc áp dụng từ: 01/09/2024
        • Kinh phí hỗ trợ: 100 tỷ VND cho các tỉnh

        ✅ KẾT LUẬN: Các trường phải báo cáo sẵn sàng vào ngày 15/08/2024.
        """,
        "issuer_name": "Bộ Giáo dục và Đào tạo",
        "issued_date": date(2024, 5, 25),
        "effective_date": date(2024, 9, 1),
        "page_count": 8,
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
    {
        "filename": "baocao_kiemtoat_2024.pdf",
        "original_filename": "Báo cáo kiểm toàn năm 2024.pdf",
        "document_type": "bao_cao",
        "document_number": "BK-2024/HN",
        "document_title": "Báo cáo kiểm toàn tài chính năm 2024 của UBND Thành phố",
        "document_summary": """
        🎯 TÓNG DÀI: Báo cáo kiểm toàn các chi tiêu ngân sách thành phố năm 2024, phát hiện sai phạm tài chính cần xử lý.

        📋 ĐIỂM CHÍNH:
        • Tổng chi tiêu: 850 tỷ VND, chi đúng kế hoạch 98.5%
        • Phát hiện sai phạm: 12 trường hợp, thu hồi 2.3 tỷ VND
        • Kiến nghị cải thiện: Tăng cường kiểm soát chi trả, xây dựng quy trình rõ ràng
        • Cần xử lý: 5 cán bộ liên quan đến sai phạm

        📌 CHI TIẾT QUAN TRỌNG:
        • Mã báo cáo: BK-2024/HN
        • Kỳ kiểm toàn: Năm 2024
        • Cơ quan thực hiện: Văn phòng Kiểm toán Thành phố
        • Tổng kiểm toàn: 120 đơn vị, 45 cơ sở giáo dục
        • Tiền phát hiện: 2.3 tỷ VND

        ✅ KẾT LUẬN: UBND phải chỉ đạo xử lý sai phạm trước 31/12/2024 và báo cáo kết quả.
        """,
        "issuer_name": "Văn phòng Kiểm toán Thành phố Hà Nội",
        "issued_date": date(2024, 4, 10),
        "effective_date": date(2024, 4, 15),
        "page_count": 24,
        "mime_type": "application/pdf",
    },
    {
        "filename": "thieuhuahuong2024.txt",
        "original_filename": "Thưởng khóa 2024 danh sách.txt",
        "document_type": "cong_van",
        "document_number": "TH-2024/BNV",
        "document_title": "Danh sách công chức đạt thành tích xuất sắc được tặng bằng khen năm 2024",
        "document_summary": """
        🎯 TÓNG DÀI: Công bố danh sách 250 công chức được tặng bằng khen vì thành tích xuất sắc trong công tác năm 2024.

        📋 ĐIỂM CHÍNH:
        • Tổng công chức được khen: 250 người
        • Từ các ngành: Giáo dục, Y tế, Công an, Tài chính
        • Hình thức khen: Bằng khen + tiền thưởng 5-10 triệu VND/người
        • Hội thao kỷ niệm: 05/06/2024 tại Hà Nội

        📌 CHI TIẾT QUAN TRỌNG:
        • Danh sách chính thức: In kèm theo
        • Thời gian trao tặng: 01-30/06/2024
        • Kinh phí: 2.5 tỷ VND cho toàn bộ
        • Lệnh tặng bằng khen: 123/2024/QĐ-BNV

        ✅ KẾT LUẬN: Các đơn vị tổ chức lễ trao tặng và báo cáo kết quả trước 15/07/2024.
        """,
        "issuer_name": "Bộ Nội vụ",
        "issued_date": date(2024, 5, 20),
        "effective_date": date(2024, 5, 25),
        "page_count": 6,
        "mime_type": "text/plain",
    },
]

DUMMY_CHUNKS = [
    {
        "chunk_index": 1,
        "section_type": "title",
        "section_title": "Quyết định số 001/2024 của UBND",
        "section_code": "001/2024",
        "page_number": 1,
        "content_preview": "Quyết định về tổ chức hoạt động quản lý tài nguyên nước toàn quốc",
        "bm25_text": "Quyết định tổ chức hoạt động quản lý tài nguyên nước toàn quốc",
    },
    {
        "chunk_index": 2,
        "section_type": "article",
        "section_code": "Điều 1",
        "section_title": "Yêu cầu, mục đích",
        "page_number": 2,
        "content_preview": "Thành lập Ban Quản lý Tài nguyên Nước trực thuộc Bộ Tài nguyên để giám sát chất lượng nước...",
        "bm25_text": "Thành lập Ban Quản lý Tài nguyên Nước trực thuộc Bộ Tài nguyên",
    },
    {
        "chunk_index": 3,
        "section_type": "article",
        "section_code": "Điều 2",
        "section_title": "Chức năng, nhiệm vụ",
        "page_number": 3,
        "content_preview": "Ban Quản lý có trách nhiệm giám sát chất lượng nước, xây dựng quy định khai thác nước ngầm...",
        "bm25_text": "Ban Quản lý chịu trách nhiệm giám sát chất lượng nước toàn quốc",
    },
    {
        "chunk_index": 4,
        "section_type": "article",
        "section_code": "Điều 5",
        "section_title": "Kinh phí thực hiện",
        "page_number": 5,
        "content_preview": "Cấp phát 50 tỷ VND từ ngân sách thành phố cho hoạt động giám sát và báo cáo hàng quý...",
        "bm25_text": "Cấp phát 50 tỷ VND ngân sách giám sát hoạt động hàng quý",
    },
]

def seed_data():
    """Tạo dữ liệu ảo vào database"""
    db = SessionLocal()
    
    try:
        # Lấy user đầu tiên (hoặc tạo user admin nếu chưa có)
        user = db.query(User).filter(User.role == "staff").first()
        if not user:
            # Nếu không có staff, lấy admin
            user = db.query(User).filter(User.role == "admin").first()
        
        if not user:
            print("❌ Không tìm thấy user nào trong database. Hãy tạo user trước.")
            return
        
        print(f"✓ Sử dụng user: {user.username} (ID: {user.id})")
        
        # Tạo documents
        created_docs = []
        for doc_data in DUMMY_DOCUMENTS:
            doc = Document(
                filename=doc_data["filename"],
                original_filename=doc_data["original_filename"],
                document_type=doc_data["document_type"],
                document_number=doc_data["document_number"],
                document_title=doc_data["document_title"],
                document_summary=doc_data["document_summary"],
                issuer_name=doc_data["issuer_name"],
                issued_date=doc_data["issued_date"],
                effective_date=doc_data["effective_date"],
                page_count=doc_data["page_count"],
                mime_type=doc_data["mime_type"],
                owner_id=user.id,
                uploaded_by=user.id,
                processed_by=user.id,
                status="completed",
                processing_status="completed",
                review_status="approved",
                language="vi",
                source_format="pdf",  # Ngắn gọn: pdf, docx, txt
                mime_type=doc_data["mime_type"],
                file_size_kb=1024,
                created_at=datetime.now() - timedelta(days=10),
                processed_at=datetime.now() - timedelta(days=9),
                updated_at=datetime.now() - timedelta(days=1),
            )
            db.add(doc)
            db.flush()
            created_docs.append(doc)
            print(f"✓ Tạo document: {doc.document_title}")
        
        db.commit()
        
        # Tạo chunks cho mỗi document
        for doc in created_docs:
            for i, chunk_data in enumerate(DUMMY_CHUNKS[:3]):  # 3 chunks cho mỗi doc
                chunk = ChunkMetadata(
                    document_id=doc.id,
                    chunk_index=chunk_data["chunk_index"] + i,
                    section_type=chunk_data["section_type"],
                    section_code=chunk_data["section_code"],
                    section_title=chunk_data["section_title"],
                    page_number=chunk_data["page_number"],
                    content_preview=chunk_data["content_preview"],
                    bm25_text=chunk_data["bm25_text"],
                    token_count=len(chunk_data["bm25_text"].split()),
                    embedding_status="completed",
                    embedding_model="fallback-384",
                    created_at=datetime.now() - timedelta(days=8),
                )
                db.add(chunk)
            print(f"  ✓ Thêm 3 chunks cho document #{doc.id}")
        
        db.commit()
        
        # Tạo summaries cho mỗi document
        for doc in created_docs:
            summary = SummaryHistory(
                document_id=doc.id,
                user_id=user.id,
                summary_type="summary",
                version_no=1,
                title=f"Tóm tắt {doc.document_title}",
                summary_text=doc.document_summary,
                prompt_template="structured_summary_4part",
                model_name="llama3.2:latest",
                groundedness_score=0.92,
                hallucination_flag=False,
                is_reviewed=True,
                reviewed_by=user.id,
                created_at=datetime.now() - timedelta(days=7),
                updated_at=datetime.now() - timedelta(days=1),
                source_chunk_ids_json=json.dumps(
                    [f"chunk_{i}" for i in range(1, 4)],
                    ensure_ascii=False
                ),
            )
            db.add(summary)
            print(f"  ✓ Tạo summary cho document #{doc.id}")
        
        db.commit()
        
        print("\n✅ Tạo dữ liệu ảo thành công!")
        print(f"   • Documents: {len(created_docs)}")
        print(f"   • Chunks: {len(created_docs) * 3}")
        print(f"   • Summaries: {len(created_docs)}")
        print("\n🎉 Hệ thống sẵn sàng hiển thị dữ liệu! Vào UI để xem.")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
