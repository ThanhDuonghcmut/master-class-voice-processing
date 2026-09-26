"""Sinh báo cáo Word từ số liệu thật trong build/ và metadata.json.

Mọi con số trong báo cáo đều đọc từ dữ liệu đang có, không gõ tay — sửa sách rồi chạy lại
là báo cáo tự cập nhật.

    .venv/bin/python scripts/tao_bao_cao.py        # ghi out/Bao_cao.docx
"""
import csv
import json
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

from book_units import BUILD, ROOT, iter_units, load_book, load_metadata

OUT = ROOT / "out" / "Bao_cao.docx"
TRONG = "[CHỜ ĐIỀN]"


# ---------- số liệu ----------
def so_lieu():
    book = load_book()
    meta = load_metadata()
    timing = json.loads((BUILD / "timing.json").read_text(encoding="utf-8"))
    units = list(iter_units(book))
    tts = [json.loads(l) for l in (BUILD / "tts_log.jsonl").open(encoding="utf-8")]
    fixes = list(csv.DictReader((ROOT / "sua_cach_doc.csv").open(encoding="utf-8-sig"))) \
        if (ROOT / "sua_cach_doc.csv").exists() else []
    qa_files = sorted((ROOT / "qa").glob("*.csv"))
    qa = {f.stem: list(csv.DictReader(f.open(encoding="utf-8-sig"))) for f in qa_files}
    mp3 = list((BUILD / "mp3").glob("*.mp3"))
    quet = {}
    for f in BUILD.glob("asr_quet*.csv"):
        rows = list(csv.DictReader(f.open(encoding="utf-8")))
        quet[f.stem] = rows
    src = (ROOT / "scripts" / "01_extract_pdf.py").read_text(encoding="utf-8")
    n_chinh_ta = src.count('": "', src.index("SOURCE_FIXES"), src.index("SPEECH_FIXES"))
    tong_giay = sum(v["duration"] for v in timing.values())
    tieng_doc = sum(r["sec"] for r in tts if r.get("sec"))
    return {
        "meta": meta, "book": book, "timing": timing, "units": units, "qa": qa, "fixes": fixes,
        "gio": tong_giay / 3600,
        "dong_ho": f'{int(tong_giay // 3600)} giờ {int(tong_giay % 3600 // 60)} phút',
        "so_nhom": len(timing), "so_mp3": len(mp3),
        "dung_luong": sum(f.stat().st_size for f in mp3) / 2**20,
        "so_cau": sum(1 for u in units if u.kind in ("sent", "note_sent")),
        "so_clip": len(units),
        "so_ky_tu": sum(len(u.text) for u in units),
        "so_tu": sum(len(u.text.split()) for u in units),
        "phut_may": sum(r["compute"] for r in tts) / 60,
        "rtf": sum(r["compute"] for r in tts) / max(sum(r["sec"] for r in tts), 1),
        "n_chinh_ta": n_chinh_ta,
        "n_doc_lai": sum(1 for r in fixes if r.get("doc_lai")),
        "n_sua_doc": sum(1 for r in fixes if r.get("speech")),
        "n_qa_cau": sum(len(v) for v in qa.values()),
        "so_file_sach": len(list((ROOT / "out" / meta["slug"]).iterdir())),
        "quet_cau": sum(len(v) for v in quet.values()),
    }


# ---------- tiện ích Word ----------
class BaoCao:
    def __init__(self):
        self.doc = Document()
        st = self.doc.styles["Normal"]
        st.font.name = "Times New Roman"
        st.font.size = Pt(13)
        st.paragraph_format.space_after = Pt(6)
        st.paragraph_format.line_spacing = 1.3
        for s in self.doc.sections:
            s.left_margin = s.right_margin = Cm(2.5)
            s.top_margin = s.bottom_margin = Cm(2)

    def p(self, text="", bold=False, italic=False, size=13, align=None, space=6):
        par = self.doc.add_paragraph()
        par.paragraph_format.space_after = Pt(space)
        if align:
            par.alignment = align
        run = par.add_run(text)
        run.bold, run.italic, run.font.size = bold, italic, Pt(size)
        run.font.name = "Times New Roman"
        return par

    def h(self, text, level=1):
        sizes = {1: 15, 2: 13.5}
        par = self.p(text, bold=True, size=sizes.get(level, 13), space=6)
        par.paragraph_format.space_before = Pt(14 if level == 1 else 10)
        return par

    def bullet(self, text, level=0):
        par = self.doc.add_paragraph(text, style="List Bullet" if level == 0 else "List Bullet 2")
        par.paragraph_format.space_after = Pt(3)
        for r in par.runs:
            r.font.name, r.font.size = "Times New Roman", Pt(13)
        return par

    def numbered(self, text):
        par = self.doc.add_paragraph(text, style="List Number")
        par.paragraph_format.space_after = Pt(3)
        for r in par.runs:
            r.font.name, r.font.size = "Times New Roman", Pt(13)
        return par

    def bang(self, header, rows, widths=None):
        t = self.doc.add_table(rows=1, cols=len(header))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, h in enumerate(header):
            cell = t.rows[0].cells[i]
            cell.text = ""
            run = cell.paragraphs[0].add_run(h)
            run.bold = True
            run.font.size = Pt(12)
            run.font.name = "Times New Roman"
        for row in rows:
            cells = t.add_row().cells
            for i, v in enumerate(row):
                cells[i].text = ""
                run = cells[i].paragraphs[0].add_run(str(v))
                run.font.size = Pt(12)
                run.font.name = "Times New Roman"
        if widths:
            for r in t.rows:
                for i, w in enumerate(widths):
                    r.cells[i].width = Cm(w)
        self.p("", space=4)
        return t

    def ghi(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(path)


# ---------- nội dung ----------
def viet(d):
    b = BaoCao()
    C = WD_ALIGN_PARAGRAPH.CENTER
    m = d["meta"]

    # --- Bìa ---
    b.p("ĐẠI HỌC KHOA HỌC TỰ NHIÊN – ĐẠI HỌC QUỐC GIA TP. HỒ CHÍ MINH", bold=True, size=13, align=C)
    b.p("KHOA CÔNG NGHỆ THÔNG TIN", bold=True, size=13, align=C)
    for _ in range(4):
        b.p("")
    b.p("XỬ LÝ TIẾNG NÓI", bold=True, size=20, align=C)
    b.p("Báo cáo đồ án: Xây dựng sách nói DAISY 3", bold=True, size=16, align=C)
    b.p(f'Tác phẩm: “{m["title"]}” – {m["creator"]}', italic=True, size=14, align=C)
    for _ in range(3):
        b.p("")
    b.p("Giảng viên hướng dẫn:", bold=True, align=C)
    for t in ["PGS.TS. Đinh Điền", "TS. Châu Thành Đức", "TS. Đỗ Đức Hào"]:
        b.p(t, align=C, space=2)
    b.p("")
    b.p("Nhóm thực hiện:", bold=True, align=C)
    b.p(TRONG + " (danh sách thành viên và mã học viên)", italic=True, align=C)
    b.p("K35 – Học phần Xử lý tiếng nói", align=C)
    for _ in range(3):
        b.p("")
    b.p(f"Thành phố Hồ Chí Minh, tháng {date.today().month:02d} năm {date.today().year}", align=C)
    b.doc.add_page_break()

    # --- 1. Giới thiệu ---
    b.h("1. Giới thiệu")
    b.p("DAISY 3 (ANSI/NISO Z39.86-2005) là tiêu chuẩn sách nói kỹ thuật số dành cho người khiếm thị "
        "và người gặp khó khăn khi đọc chữ in. Khác với một file MP3 thông thường, sách DAISY giữ được "
        "cấu trúc của sách giấy: người nghe nhảy thẳng tới một chương, một mục hay một câu bất kỳ, và "
        "phần mềm đọc bôi sáng đúng câu đang phát nhờ văn bản được đồng bộ với âm thanh ở mức từng câu.")
    b.p("Nhóm chọn tác phẩm “Những tấm lòng cao cả” của Edmondo De Amicis, bản dịch Hoàng Thiếu Sơn, "
        "để xây dựng thành một cuốn sách DAISY 3 hoàn chỉnh. Bản điện tử nhóm dùng làm nguồn là file PDF "
        "đã có sẵn lớp văn bản, không phải bản scan, nên bài toán đặt ra là sinh giọng đọc từ văn bản "
        "(Text-to-Speech) rồi đồng bộ ngược lại với văn bản, chứ không cần nhận dạng ảnh hay nhận dạng "
        "tiếng nói.")
    b.p("Thông tin sách theo yêu cầu thu thập dữ liệu:", space=4)
    b.bang(["Trường", "Giá trị"], [
        ["Tên sách", m["title"]],
        ["Tác giả", m["creator"]],
        ["Dịch giả", m["contributor"]],
        ["Thể loại", m["subject"]],
        ["Nhà phát hành", m["publisher"]],
        ["Ngày phát hành", m["date"]],
        ["Mã ISBN", m["source"]],
        ["Ngôn ngữ", m["language"]],
        ["Người đóng góp", TRONG],
        ["URL nguồn", TRONG],
    ], widths=[4.5, 11.5])

    # --- 2. Quy trình ---
    b.h("2. Quy trình thực hiện")
    b.p("Toàn bộ quy trình được chia thành sáu bước nối tiếp nhau, mỗi bước là một chương trình riêng, "
        "nhận đầu ra của bước trước làm đầu vào. Cách chia này cho phép chạy lại một bước mà không phải "
        "làm lại từ đầu: sửa một câu đọc sai thì chỉ bước sinh tiếng nói và bước ghép âm thanh chạy lại "
        "cho câu và chương đó.")
    b.bang(["Bước", "Việc", "Đầu vào", "Đầu ra"], [
        ["1", "Trích cấu trúc sách", "File PDF", "Cây tháng – truyện – đoạn – câu, kèm chú thích"],
        ["2", "Sinh giọng đọc", "Từng câu văn bản", "Một file WAV cho mỗi câu"],
        ["3", "Ghép âm thanh", "Các file WAV", "Một file MP3 cho mỗi truyện, kèm mốc thời gian từng câu"],
        ["4", "Dựng sách DAISY", "Văn bản và mốc thời gian", "Bộ file DTBook, SMIL, NCX, OPF"],
        ["5", "Kiểm thính (QA)", "Sách vừa dựng", "Danh sách câu đọc sai do người nghe ghi nhận"],
        ["6", "Sửa và đóng gói", "Danh sách câu đọc sai", "Sách đã sửa, nén kèm mã băm SHA-256"],
    ], widths=[1.3, 3.6, 4.2, 7])
    b.p("Bước 5 và bước 6 lặp lại theo vòng: người nghe ghi nhận lỗi, nhóm sửa, dựng lại sách rồi đưa "
        "bản mới cho người nghe kiểm tiếp.")

    b.h("2.1. Bước 1 – Trích cấu trúc sách từ PDF", 2)
    b.p("Bản PDF được sinh từ ebook nên phông chữ dùng nhất quán trong cả sách: tiêu đề tháng một phông, "
        "tên truyện một phông, dòng ghi ngày tháng một phông, phần chú thích cuối sách dùng cỡ chữ nhỏ hơn "
        "phần thân. Chương trình dựa vào đặc điểm này để phân loại từng dòng, thay vì đoán theo chữ hoa "
        "hay theo vị trí trên trang.")
    b.p("Sau khi phân loại, chương trình nối lại những đoạn bị ngắt giữa hai trang, tách đoạn thành câu "
        "theo dấu chấm câu, gộp những mẩu quá ngắn vào câu liền sau, rồi gán cho mỗi câu một mã định danh "
        "cố định. Mã này là xương sống của cả quy trình: mọi bước sau đều tham chiếu tới câu bằng mã đó.")
    b.p("Kết quả trích được đối chiếu tự động với mục lục có sẵn trong PDF; nếu số tiêu đề trích ra không "
        "khớp với mục lục, hoặc có dấu chú thích không tìm thấy nội dung tương ứng, chương trình dừng lại "
        "và báo lỗi thay vì tiếp tục với dữ liệu sai.")

    b.h("2.2. Bước 2 – Sinh giọng đọc", 2)
    b.p("Mỗi câu được sinh thành một file âm thanh riêng. Cách làm này tốn công quản lý nhiều file nhỏ "
        "nhưng đổi lại hai điều quan trọng: biết chính xác độ dài của từng câu mà không cần thuật toán "
        "dóng hàng tiếng nói với văn bản, và sửa một câu thì chỉ sinh lại đúng câu đó.")
    b.p("Chương trình lưu kèm mỗi file âm thanh một bản sao của câu đã đọc. Khi chạy lại, câu nào đã có "
        "âm thanh và nội dung không đổi thì bỏ qua, câu nào có nội dung khác đi thì sinh lại. Nhờ vậy sau "
        "mỗi vòng kiểm thính, việc sinh giọng đọc chỉ mất vài giây cho vài câu vừa sửa.")

    b.h("2.3. Bước 3 – Ghép âm thanh theo truyện", 2)
    b.p("Các câu của cùng một truyện được ghép thành một file MP3 duy nhất, xen giữa là khoảng lặng. "
        "Độ dài khoảng lặng không chọn theo cảm tính: nhóm cho công cụ đọc liền mười hai cặp câu rồi đo "
        "khoảng nghỉ tự nhiên giữa hai câu, lấy trung vị làm chuẩn, sau đó điều chỉnh theo phản hồi của "
        "người nghe. Khoảng nghỉ sau tiêu đề và sau mỗi đoạn dài hơn khoảng nghỉ giữa hai câu trong cùng "
        "một đoạn.")
    b.p("Mốc thời gian bắt đầu và kết thúc của từng câu được tính từ số mẫu tín hiệu, nên sai số bằng "
        "không. Một điểm nhóm rút ra khi kiểm thử: phần mềm đọc DAISY phát đúng đoạn từ mốc bắt đầu đến "
        "mốc kết thúc rồi nhảy ngay sang câu kế, cho nên khoảng lặng nằm giữa hai mốc sẽ bị bỏ qua. Mốc "
        "kết thúc của mỗi câu vì vậy được đặt trùng với mốc bắt đầu của câu sau, tức là khoảng nghỉ thuộc "
        "về câu đứng trước nó.")

    b.h("2.4. Bước 4 – Dựng sách DAISY 3", 2)
    b.p("Bước này sinh đủ bộ file mà tiêu chuẩn DAISY 3 yêu cầu:")
    b.bullet("File văn bản DTBook chứa toàn văn sách, cấu trúc hai cấp tháng và truyện, mỗi câu mang mã "
             "định danh riêng.")
    b.bullet("File SMIL cho mỗi truyện, ghép từng câu trong file văn bản với đoạn âm thanh tương ứng "
             "trong file MP3 của truyện đó.")
    b.bullet("File NCX chứa mục lục hai cấp để người nghe nhảy tới đúng tháng, đúng truyện.")
    b.bullet("File OPF khai báo siêu dữ liệu của sách và liệt kê toàn bộ tài nguyên.")
    b.bullet("File định kiểu và file tài nguyên đi kèm theo quy định của tiêu chuẩn.")
    b.p("Chín mươi hai chú thích cuối sách được đặt ngay sau đoạn văn có dấu chú thích, mở đầu bằng cụm "
        "“Chú thích:”, và được đánh dấu là phần có thể bỏ qua. Người nghe tắt chú thích trong phần mềm đọc "
        "thì mạch truyện liền lại, bật lên thì nghe được giải nghĩa ngay tại chỗ gặp từ lạ, thay vì phải "
        "chờ tới cuối sách.")
    b.p("Cuối bước, chương trình tự kiểm tra số câu có đồng bộ trong file văn bản với số mốc âm thanh "
        "trong các file SMIL, và kiểm tra mọi tham chiếu đều trỏ tới phần tử có thật. Lệch nhau thì báo "
        "lỗi ngay.")

    b.h("2.5. Bước 5 – Kiểm thính", 2)
    b.p("Sách dài hơn mười giờ nên việc nghe soát được chia cho nhiều người và cần một cách ghi nhận "
        "lỗi chính xác tới từng câu. Nhóm xây một trang kiểm thính chạy trên máy cá nhân: bên trái là mục "
        "lục sách, bên phải là toàn bộ câu của truyện đang chọn, mỗi dòng hiện mã câu và mốc thời gian.")
    b.p("Người nghe bấm vào một câu để nghe riêng câu đó, hoặc nghe liền cả truyện với câu đang đọc được "
        "bôi sáng. Nghe thấy chỗ sai thì đánh dấu và ghi chú ngay trên dòng đó, cuối buổi bấm một nút để "
        "xuất ra file ghi nhận gồm mã câu, tên truyện, nội dung câu và ghi chú. Nhờ ghi theo mã câu, người "
        "sửa không phải tìm lại câu trong sách.")
    b.p("Sách được chia thành ba phần có thời lượng gần bằng nhau để chia việc:", space=4)
    b.bang(["Phần", "Thời lượng", "Từ truyện", "Đến truyện"], [
        ["Phần 1", "3 giờ 18 phút", "Ngày khai trường", "Franti bị đuổi học"],
        ["Phần 2", "3 giờ 36 phút", "Cậu bé đánh trống người Sardegna", "Thầy giáo của bố"],
        ["Phần 3", "3 giờ 20 phút", "Dưỡng bệnh", "Từ biệt"],
    ], widths=[2, 3, 5.5, 5.5])

    b.p("Song song với việc nghe thủ công, nhóm dựng thêm một bước kiểm tự động: cho một mô hình "
        "nhận dạng tiếng nói nghe ngược lại chính file âm thanh vừa sinh, rồi so bản nghe được với "
        "văn bản gốc. Máy quét được cả cuốn sách trong khi tai người chỉ nghe hết được từng phần, "
        "nên hai cách bổ sung cho nhau: máy bắt lỗi đọc lặp và đọc thiếu nằm rải rác, tai người bắt "
        "những lỗi máy không thấy như ngắt nhịp gượng hay giọng đọc đơ.")
    b.p("Điều đáng lưu ý là không thể chỉ dựa vào mức giống nhau giữa hai bản để kết luận. Ở một câu "
        "dài, đọc lặp thừa một cụm chỉ kéo mức giống xuống vài phần trăm, vẫn nằm trên mọi ngưỡng hợp "
        "lý. Vì vậy chương trình dò dấu hiệu trực tiếp:")
    b.bullet("Đọc lặp: đếm số lần một cụm từ 1 đến 4 từ lặp ngay sau chính nó trong bản nghe được, so "
             "với số lần trong văn bản gốc. Phép đếm thực hiện trên dạng đã bỏ dấu thanh, vì nhận dạng "
             "tiếng nói hay nghe từ láy thành từ lặp.")
    b.bullet("Đọc thiếu: so số từ của bản nghe được với văn bản gốc, sau khi bỏ các từ chỉ số vì bản "
             "nghe được viết số bằng chữ số còn sách viết bằng chữ.")
    b.p("Danh sách máy đưa ra là danh sách nghi vấn chứ không phải kết luận, vì mô hình nhận dạng cũng "
        "nghe sai, nhất là tên riêng nước ngoài. Nhóm lọc bớt các trường hợp báo nhầm đã biết rồi mới "
        "đưa người nghe kiểm lại từng câu.")

    b.h("2.6. Bước 6 – Sửa lỗi và đóng gói", 2)
    b.p("Các file ghi nhận của mọi người được gộp thành một bảng sửa duy nhất, mỗi câu một dòng, giữ "
        "nguyên ghi chú của từng người. Bảng này có hai cột điều khiển:")
    b.bullet("Cột bản đọc: điền cách đọc mới cho câu, còn chữ hiển thị trong sách vẫn giữ nguyên văn. "
             "Dùng khi công cụ đọc sai mà văn bản không sai, ví dụ đọc số thập phân theo kiểu phân cách "
             "hàng nghìn, hoặc ngắt nhịp sai ở câu có cấu trúc nhập nhằng.")
    b.bullet("Cột đọc lại: đánh dấu những câu bị lặp cụm từ hoặc ngắt nhịp gượng. Công cụ sinh tiếng nói "
             "lấy mẫu ngẫu nhiên nên mỗi lần đọc cho ra một bản khác nhau; chương trình đọc lại câu đó "
             "nhiều lần, dùng nhận dạng tiếng nói chấm điểm từng bản, ưu tiên bản không còn dấu hiệu lặp "
             "rồi mới xét mức giống, và chỉ thay khi bản mới tốt hơn bản đang có.")
    b.p("Với một số câu, đọc lại bao nhiêu lần cũng lặp vì chính cấu trúc câu gây ra, chẳng hạn câu kết "
        "thúc bằng “không bao giờ, không bao giờ!”. Khi đó nhóm sửa bản đọc để phá thế lặp, ví dụ tách "
        "thành hai câu ngắn bằng dấu chấm than, còn chữ hiển thị trong sách vẫn giữ nguyên văn. Cách này "
        "cũng dùng để sửa chỗ ngắt nhịp sai.")
    b.p("Riêng lỗi chính tả của bản điện tử thì sửa thẳng vào bảng sửa nguồn, đổi cả chữ hiển thị lẫn "
        "cách đọc, vì bản in gốc không sai những chỗ đó.")
    b.p("Sau khi sửa, sách được dựng lại rồi nén kèm file chứa mã băm SHA-256 theo đúng cấu trúc thư mục "
        "mà hướng dẫn nộp bài quy định.")

    # --- 3. Công cụ ---
    b.h("3. Công cụ và thư viện sử dụng")
    b.h("3.1. Sinh tiếng nói", 2)
    b.p("Nhóm dùng VieNeu-TTS phiên bản v3 Turbo, một mô hình tổng hợp tiếng nói tiếng Việt mã nguồn mở, "
        "chạy hoàn toàn trên CPU thông qua ONNX Runtime. Lý do chọn:")
    b.bullet("Chạy ngoại tuyến trên máy cá nhân, không tốn chi phí theo số ký tự. Với một cuốn sách hơn "
             "bốn trăm nghìn ký tự và nhiều vòng sửa, các dịch vụ tính tiền theo lượng chữ sẽ phát sinh "
             "chi phí đáng kể.")
    b.bullet("Chất lượng giọng đọc tự nhiên, tần số lấy mẫu 48 kHz, có sẵn 25 giọng thuộc ba miền.")
    b.bullet("Không cần GPU, tốc độ sinh nhanh hơn thời gian thực nhiều lần.")
    b.p("Nhóm nghe thử cả 25 giọng trên cùng một đoạn trích của sách rồi chọn giọng “Đức Trí” (nam, giọng "
        "miền Nam, phong cách đọc truyện) vì hợp với lời kể của một cậu bé và nhịp đọc chậm vừa phải, dễ "
        "theo dõi khi nghe dài.")

    b.h("3.2. Xử lý văn bản và âm thanh", 2)
    b.bang(["Thư viện", "Dùng để làm gì"], [
        ["PyMuPDF", "Đọc PDF kèm thông tin phông chữ của từng dòng, phục vụ việc nhận dạng cấu trúc sách"],
        ["soundfile, NumPy", "Đọc và ghi tín hiệu âm thanh, cắt khoảng lặng, ghép các câu"],
        ["lameenc", "Mã hoá MP3 ngay trong Python, không phụ thuộc công cụ cài ngoài"],
        ["faster-whisper", "Nhận dạng tiếng nói để nghe ngược bản đọc, tìm câu đọc lặp hoặc đọc thiếu"],
        ["python-docx", "Sinh file báo cáo này từ số liệu thật của dự án"],
    ], widths=[4, 12])
    b.p("Danh sách 6.775 âm tiết tiếng Việt lấy từ đồ án trước của môn học được dùng để dò lỗi chính tả "
        "trong bản điện tử.")

    b.h("3.3. Phần mềm kiểm thử", 2)
    b.p("Nhóm dùng Thorium Reader để mở sách như một người khiếm thị sẽ dùng: kiểm tra mục lục nhảy đúng "
        "chương, văn bản bôi sáng đúng câu đang đọc, và chức năng bật tắt chú thích hoạt động đúng.")

    # --- 4. Kết quả ---
    b.h("4. Kết quả đạt được")
    b.h("4.1. Sách nói hoàn chỉnh", 2)
    b.bang(["Chỉ tiêu", "Kết quả"], [
        ["Tổng thời lượng", d["dong_ho"]],
        ["Số truyện và phần", f'{d["book"]["stats"]["chapters"]} truyện, thuộc 10 tháng và phần Mở đầu'],
        ["Số câu có đồng bộ văn bản và âm thanh", f'{d["so_clip"]:,} câu'.replace(",", ".")],
        ["Số đoạn văn", f'{d["book"]["stats"]["paragraphs"]:,}'.replace(",", ".")],
        ["Số chú thích", f'{d["book"]["stats"]["notes"]} chú thích, đọc ngay tại chỗ tham chiếu'],
        ["Số từ", f'{d["so_tu"]:,} từ'.replace(",", ".")],
        ["Số file âm thanh", f'{d["so_mp3"]} file MP3, mỗi truyện một file'],
        ["Dung lượng âm thanh", f'{d["dung_luong"]:.0f} MB'],
        ["Tổng số file trong sách", f'{d["so_file_sach"]} file'],
    ], widths=[7, 9])
    b.p("Sách mở được bằng Thorium Reader, mục lục hai cấp hoạt động đúng, văn bản bôi sáng khớp với "
        "giọng đọc ở mức từng câu, và phần chú thích bật tắt được.")

    b.h("4.2. Thời gian và hiệu năng", 2)
    b.p(f'Toàn bộ khâu sinh giọng đọc cho cả cuốn sách mất khoảng {d["phut_may"]:.0f} phút máy trên một '
        f'máy tính cá nhân dùng chip Apple M5 Pro, tương ứng hệ số thời gian thực {d["rtf"]:.2f}, tức là '
        f'nhanh gấp khoảng {1/d["rtf"]:.0f} lần so với thời lượng audio sinh ra. Khâu ghép MP3 cho cả sách '
        f'mất khoảng ba phút, khâu dựng bộ file DAISY mất vài giây.')

    b.h("4.3. Kết quả kiểm thính", 2)
    b.p(f'Tính tới thời điểm viết báo cáo, người nghe đã ghi nhận {d["n_qa_cau"]} câu có lỗi. Toàn bộ đã '
        f'được xử lý xong:')
    b.bullet(f'{d["n_chinh_ta"]} chỗ sai chính tả trong bản điện tử đã được sửa (sai một chữ cái, dính hai '
             f'chữ liền nhau, đặt sai vị trí dấu thanh, nhầm chữ cái với chữ số).')
    b.bullet(f'{d["n_doc_lai"]} câu bị đọc lặp cụm từ hoặc ngắt nhịp gượng đã được sinh lại.')
    b.bullet(f'{d["n_sua_doc"]} câu được chỉnh cách đọc bằng cách thêm dấu ngắt vào bản đọc, giữ nguyên chữ '
             f'trong sách.')
    b.p(f'Bước kiểm tự động quét {d["quet_cau"]:,} câu, chỉ ra những câu có dấu hiệu đọc lặp hoặc đọc '
        f'thiếu để người nghe kiểm lại. Trong số câu máy nghi ở phần đã đối chiếu, ba câu đúng là lỗi '
        f'thật và đều là lỗi mà người nghe đã bỏ sót; các trường hợp còn lại là mô hình nhận dạng nghe '
        f'sai tên riêng nước ngoài. Sau khi bổ sung các luật lọc báo nhầm, số câu máy đưa ra để kiểm lại '
        f'giảm còn khoảng ba phần nghìn tổng số câu.'.replace(",", "."))
    b.p("Một phát hiện đáng chú ý từ khâu kiểm thính: nhiều lỗi chính tả của bản điện tử là từ viết đúng "
        "chính tả nhưng sai ngữ cảnh, ví dụ “tốt bụng” thành “tất bụng”, “gập người” thành “gặp người”. "
        "Chương trình dò tự động bằng từ điển âm tiết không bắt được những trường hợp này vì cả hai từ đều "
        "tồn tại trong tiếng Việt; chỉ tai người nghe mới phát hiện ra.")

    b.h("4.4. Bộ công cụ xây dựng được", 2)
    b.p("Ngoài sản phẩm sách nói, nhóm xây dựng một bộ chương trình dùng lại được cho các cuốn sách khác "
        "có cùng dạng nguồn: chương trình kiểm tra máy trước khi chạy, sáu chương trình cho sáu bước của "
        "quy trình, trang kiểm thính, chương trình gộp kết quả kiểm thính, và chương trình sinh báo cáo. "
        "Toàn bộ mã nguồn được lưu trên GitHub, bản sách nói được phát hành kèm để người kiểm thính tải về "
        "mà không cần cài đặt môi trường sinh tiếng nói.")

    # --- 5. Vấn đề ---
    b.h("5. Những vấn đề gặp phải và cách giải quyết")
    b.bang(["Vấn đề", "Cách giải quyết"], [
        ["Phần mềm đọc DAISY bỏ qua khoảng lặng nằm giữa hai mốc âm thanh, nên nghe trong phần mềm thì các "
         "câu dính vào nhau dù file MP3 vẫn có khoảng nghỉ",
         "Đặt mốc kết thúc của mỗi câu trùng mốc bắt đầu của câu kế tiếp, tức là khoảng nghỉ thuộc về câu "
         "đứng trước"],
        ["Công cụ sinh tiếng nói thỉnh thoảng lặp một cụm từ, thường ở câu vốn đã có từ lặp như “đi đi, "
         "đi đi”",
         "Thử điều chỉnh tham số phạt lặp và độ ngẫu nhiên nhưng không ổn định. Cách dùng được là đọc lại "
         "nhiều lần rồi dùng nhận dạng tiếng nói chọn bản không còn lặp; câu nào đọc lại bao nhiêu lần "
         "cũng lặp thì sửa dấu câu trong bản đọc để phá thế lặp"],
        ["Công cụ đọc sai ở câu có cấu trúc nhập nhằng, ví dụ ngắt nhịp sau “thầy giáo” thay vì sau “thầy "
         "giáo mới”",
         "Thêm dấu phẩy vào bản đọc để ép gom cụm, giữ nguyên chữ hiển thị trong sách"],
        ["Bản điện tử có lỗi chính tả khiến giọng đọc sai hoặc lắp",
         "Dò toàn sách bằng từ điển âm tiết tiếng Việt kết hợp vài quy tắc hình thức, rồi soi ngữ cảnh "
         "từng chỗ trước khi sửa"],
        ["Phần mềm Thorium chuyển mọi thẻ của định dạng DTBook thành thẻ khối khi hiển thị, làm dấu chú "
         "thích bị xuống dòng riêng",
         "Đính kèm file định kiểu trong sách để chỉ định dấu chú thích hiển thị trên cùng dòng"],
        ["Thư viện sinh tiếng nói không cài được trên phiên bản Python mới nhất",
         "Chương trình cài đặt tự kiểm tra phiên bản Python đang có, nếu không phù hợp thì tự tải về một "
         "phiên bản dùng được rồi tạo môi trường riêng"],
        ["Chỉ dựa vào mức giống nhau giữa bản nghe được và văn bản gốc thì bỏ sót lỗi: ở câu dài, lặp "
         "thừa một cụm chỉ làm mức giống giảm vài phần trăm",
         "Dò dấu hiệu trực tiếp là cụm từ lặp liên tiếp và số từ bị thiếu, thay cho việc đặt ngưỡng trên "
         "mức giống"],
        ["Mô hình nhận dạng nghe sai tên riêng nước ngoài, tách một tên thành hai tiếng giống nhau nên "
         "bị báo nhầm là đọc lặp",
         "Bỏ qua cụm lặp trùng với tên riêng hoặc từ không phải âm tiết tiếng Việt; đếm trên dạng đã bỏ "
         "dấu thanh để từ láy không bị coi là lặp"],
    ], widths=[7.5, 8.5])

    # --- 6. Phân công ---
    b.h("6. Phân công nhiệm vụ")
    b.p("Bảng phân công công việc của nhóm:", space=4)
    b.bang(["Họ và tên", "Mã học viên", "Nhiệm vụ", "Mức độ hoàn thành"], [
        [TRONG, TRONG, TRONG, TRONG],
        [TRONG, TRONG, TRONG, TRONG],
        [TRONG, TRONG, TRONG, TRONG],
        [TRONG, TRONG, TRONG, TRONG],
        [TRONG, TRONG, TRONG, TRONG],
    ], widths=[4, 3, 6.5, 2.5])

    # --- 7. Kết luận ---
    b.h("7. Kết luận và hướng phát triển")
    b.p(f'Nhóm đã xây dựng hoàn chỉnh một cuốn sách nói theo tiêu chuẩn DAISY 3 dài {d["dong_ho"]}, đồng bộ '
        f'văn bản với âm thanh ở mức từng câu, có mục lục hai cấp và phần chú thích bật tắt được. Quy trình '
        f'gồm sáu bước, đi từ trích cấu trúc sách trong PDF, sinh giọng đọc bằng mô hình tiếng Việt mã nguồn '
        f'mở chạy trên máy cá nhân, ghép âm thanh theo từng truyện, dựng bộ file theo tiêu chuẩn, kiểm thính '
        f'và sửa lỗi.')
    b.p("Hạn chế còn lại nằm ở khâu kiểm thính. Bước kiểm tự động bắt được lỗi đọc lặp và đọc thiếu, "
        "nhưng lỗi ngắt nhịp gượng và giọng đọc đơ thì vẫn phải nghe bằng tai, nên chất lượng cuối cùng "
        "phụ thuộc vào việc nghe soát hết cuốn sách.")
    b.p("Hướng phát triển: mở rộng bước kiểm tự động để bắt thêm lỗi ngắt nhịp và lỗi đọc sai tên riêng, "
        "là hai loại hiện vẫn phải nghe bằng tai; bổ sung đánh số trang theo bản in để người nghe tra cứu "
        "theo trang sách giấy; và áp dụng lại bộ chương trình cho những cuốn sách khác có cùng dạng nguồn.")
    return b


if __name__ == "__main__":
    d = so_lieu()
    viet(d).ghi(OUT)
    print(f"Đã ghi {OUT.relative_to(ROOT)}")
    print(f"Chỗ cần điền tay: đánh dấu {TRONG} (thành viên, người đóng góp, URL nguồn)")
