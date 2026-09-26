"""Bước 1: PDF → build/book.json (cấu trúc tháng → truyện → đoạn → câu, kèm chú thích).

Nhận diện cấu trúc theo FONT chứ không đoán theo chữ hoa/vị trí — PDF do calibre sinh,
font nhất quán 100% (khảo sát trong KE-HOACH.md):
    Arial-BoldMT 21            → tiêu đề cấp 1 (tháng, "MỞ ĐẦU")
    Arial-BoldItalicMT 16      → tiêu đề cấp 2 (tên truyện)
    TimesNewRomanPS-BoldItal 16 ngay sau h2 → dòng ngày tháng ("Torino, thứ hai 17")
    TimesNewRomanPS-BoldItal 21 → "Hết" (bỏ)
    size 12                    → vùng chú thích cuối sách, mẫu "[n]" + nội dung
    còn lại size 16            → đoạn văn

Chạy:  .venv/bin/python scripts/01_extract_pdf.py
"""
import json
import re
import sys
from pathlib import Path

# Console Windows mặc định không phải UTF-8 → in tiếng Việt vào file/pipe sẽ lỗi
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "input" / "nhung-tam-long-cao-ca.pdf"
OUT = ROOT / "build" / "book.json"
FIXES_CSV = ROOT / "sua_cach_doc.csv"   # id,speech,ghi_chu — sửa BẢN ĐỌC từng câu theo id, chữ hiển thị giữ nguyên

FIRST_BODY_PAGE = 7  # trang 1-6: bìa, thông tin ebook, mục lục — không đọc

# Dấu kết câu; câu mới bắt đầu bằng chữ hoa, số, ngoặc kép mở hoặc gạch đầu dòng hội thoại
# Không tách trước "- ông ta nói": gạch ngang + chữ thường là lời dẫn của câu hội thoại
SENT_END = re.compile(r'(?:(?<=[.!?…])|(?<=[.!?…][”’"\)]))\s+'
                      r'(?=[“"A-ZÀ-ỸĐ0-9]|[\-–—]\s*[“"A-ZÀ-ỸĐ0-9])')
NOTE_MARK = re.compile(r"\[(\d+)\]")
# Dòng ngày trong sách cụt ("Thứ ba 18"); nghe khó hiểu → bản đọc thêm "ngày": "Thứ ba, ngày 18"
DATELINE_DAY = re.compile(r"\b([Tt]hứ (?:hai|ba|tư|năm|sáu|bảy)|[Cc]húa nhật) (\d{1,2})\b")
MIN_SENT_CHARS = 12  # câu ngắn hơn ("Ôi!") gộp vào câu kế: TTS dễ lảm nhảm với 1-2 tiếng

# Lỗi trong PDF nguồn, sửa trước khi tách câu. Mỗi dòng phải có lý do.
SOURCE_FIXES = {
    "châu u ": "châu Âu ",   # calibre làm mất chữ "Â" hoa (chỉ 1 chỗ, đã rà toàn sách)
    "4,444 km": "4 phẩy 444 km",  # VieNeu coi dấu phẩy là phân cách nghìn → "bốn nghìn"; chỗ duy nhất có số lẻ
    # Lỗi chính tả của bản ebook (calibre/OCR). Rà toàn sách bằng scripts/data/am_tiet_tieng_viet.txt
    # (danh sách 6.775 âm tiết) + luật "âm tiết không thể có 2 dấu thanh"; mỗi chỗ đã soi ngữ cảnh.
    # Sửa cả chữ hiển thị vì sách in chắc chắn không sai những chỗ này.
    "cổng chmh": "cổng chính",
    "chỉ đuờng phố": "chỉ đường phố",
    "chen nhau đểđược": "chen nhau để được",
    "nhiêu ngườí Ý": "nhiêu người Ý",
    "mỉm cuời": "mỉm cười",
    "nhìn theo eậu bé": "nhìn theo cậu bé",
    "hình như eả hai": "hình như cả hai",
    "thành hai dãý": "thành hai dãy",
    "ghen tị lụồn vào": "ghen tị luồn vào",
    "chịu đựng, rồị vừa": "chịu đựng, rồi vừa",
    "đựng mọỉ sự": "đựng mọi sự",
    "những tìếng kêu": "những tiếng kêu",
    "Venezia, ngưởi Lombardia": "Venezia, người Lombardia",
    "lòng đầy can dảm": "lòng đầy can đảm",
    "chờ dón con mình": "chờ đón con mình",
    "thiếu lễ dộ": "thiếu lễ độ",
    "nuôi gia dình": "nuôi gia đình",
    "trong sưởng thủy tinh": "trong xưởng thủy tinh",
    "muốn khuyu, đầu gục": "muốn khuỵu, đầu gục",
    "chẳng có gì bất điệt": "chẳng có gì bất diệt",
    "một vờng hoa lớn": "một vòng hoa lớn",
    "De Amlcis": "De Amicis",          # OCR: i → l
    "DeAmicis rất": "De Amicis rất",   # dính hai chữ
    "Hà Lan (l874)": "Hà Lan (1874)",  # OCR: số 1 → chữ l, TTS đọc thành chữ cái
    "sociale, l894": "sociale, 1894",
    "Gặp người lại mà tụt": "Gập người lại mà tụt",   # ố→ấ, ậ→ặ: lỗi hệ thống của bản ebook
    "cậu bé tất bụng": "cậu bé tốt bụng",
    "tình bạn tất của": "tình bạn tốt của",
    "trở về thành'phố": "trở về thành phố",           # dấu nháy lọt giữa từ
}

# Chỉ đổi BẢN ĐỌC, giữ nguyên chữ hiển thị — dùng cho từ mà TTS phát âm sai.
# tata = "bố" trong tiếng vùng Napoli (chú thích 31), xuất hiện 21 lần kể cả tiêu đề truyện;
# VieNeu đọc "tata" thành "tót ta" hoặc nuốt còn "ta" → gạch nối ép đọc rõ hai âm tiết.
SPEECH_FIXES = {"tata": "ta-ta", "Tata": "Ta-ta"}


def line_kind(line):
    """Phân loại một dòng theo font chủ đạo (tính theo số ký tự)."""
    fonts = {}
    for s in line["spans"]:
        key = (s["font"], round(s["size"]))
        fonts[key] = fonts.get(key, 0) + len(s["text"])
    font, size = max(fonts, key=fonts.get)
    if size == 12:
        return "note"
    if font == "Arial-BoldMT" and size == 21:
        return "h1"
    if font == "Arial-BoldItalicMT":
        return "h2"
    if font == "TimesNewRomanPS-BoldItal":
        return "het" if size == 21 else "bolditalic"
    return "body"                    # thường, nghiêng, hoặc trộn — đều là đoạn văn


def block_runs(block):
    """Tách block thành các run (kind, text) gồm những dòng liên tiếp cùng loại.

    Cần thiết vì pymupdf gộp tiêu đề ngắn ("Mẹ tôi") chung block với dòng ngày
    dài hơn; nếu lấy font chủ đạo của cả block thì mất tiêu đề.
    """
    if block["type"] != 0:
        return []
    runs = []
    for line in block["lines"]:
        txt = "".join(s["text"] for s in line["spans"]).strip()
        if not txt:
            continue
        kind = line_kind(line)
        if runs and runs[-1][0] == kind:
            runs[-1][1].append(txt)
        else:
            runs.append((kind, [txt]))
    return [(k, re.sub(r"\s+", " ", " ".join(ls)).strip()) for k, ls in runs]


def split_sentences(text):
    for bad, good in SOURCE_FIXES.items():
        text = text.replace(bad, good)
    sents = [s.strip() for s in SENT_END.split(text) if s.strip()]
    merged = []
    for s in sents:                       # gộp câu quá ngắn vào câu liền sau
        if merged and len(merged[-1]) < MIN_SENT_CHARS:
            merged[-1] += " " + s
        else:
            merged.append(s)
    if len(merged) >= 2 and len(merged[-1]) < MIN_SENT_CHARS:
        last = merged.pop()               # câu cuối quá ngắn thì gộp ngược
        merged[-1] += " " + last
    return merged


def speech_of(raw):
    """Bản đọc: bỏ dấu chú thích [n], áp SPEECH_FIXES (chữ hiển thị giữ nguyên)."""
    text = NOTE_MARK.sub("", raw).strip()
    for bad, good in SPEECH_FIXES.items():
        text = re.sub(rf"\b{re.escape(bad)}\b", good, text)
    return text


def ends_open(text):
    """Đoạn chưa kết thúc (bị cắt bởi ngắt trang) nếu không tận cùng bằng dấu câu."""
    return not re.search(r'[.!?…:”’"\)]$', text)


class Book:
    def __init__(self):
        self.levels = []          # level1: tháng / Mở đầu
        self.notes_raw = []       # dòng text vùng chú thích
        self.n_para = self.n_sent = 0
        self.last_kind = None     # 'h1' | 'h2' | 'p' | 'dateline'
        self.carry = False        # đoạn cuối trang trước chưa kết thúc

    # --- nơi chứa đoạn hiện tại: truyện nếu có, không thì tháng/Mở đầu ---
    def _container(self):
        lv1 = self.levels[-1]
        return lv1["chapters"][-1] if lv1["chapters"] else lv1

    def add_h1(self, text):
        self.levels.append({"id": f"lv1-{len(self.levels)+1:02d}", **self._heading(text),
                            "paragraphs": [], "chapters": []})
        self.last_kind, self.carry = "h1", False

    def add_h2(self, text):
        lv1 = self.levels[-1]
        n = sum(len(l["chapters"]) for l in self.levels) + 1
        lv1["chapters"].append({"id": f"lv2-{n:03d}", **self._heading(text), "dateline": None,
                                "paragraphs": []})
        self.last_kind, self.carry = "h2", False

    def add_dateline(self, text):
        holder = self._container()
        if holder["dateline"]:            # "(thư của bố)" và "Thứ năm 10" ở hai block khác nhau
            text = holder["dateline"]["raw"] + " " + text
            self.n_sent -= 1
        # Đổi cả chữ hiển thị (không chỉ bản đọc) để chữ bôi sáng khớp tiếng; [n] vẫn giữ trong raw
        text = DATELINE_DAY.sub(r"\1, ngày \2", text).replace("Torino[2] thứ", "Torino[2], thứ")
        holder["dateline"] = self._sentence(text)
        self.last_kind, self.carry = "dateline", False

    def add_paragraph(self, text):
        paras = self._container()["paragraphs"]
        # Nối vào đoạn trước khi đoạn đó chưa kết thúc và (a) vừa qua ngắt trang, hoặc
        # (b) block mới bắt đầu bằng chữ thường — pymupdf tách block khi có span chú
        # thích [n] làm đổi chiều cao dòng ("...bậc sơ" / "đẳng[39].")
        prev_open = bool(paras) and self.last_kind == "p" and ends_open(paras[-1]["raw"])
        if prev_open and (self.carry or text[0].islower()):
            paras[-1]["raw"] += " " + text
        else:
            self.n_para += 1
            paras.append({"id": f"p{self.n_para:05d}", "raw": text})
        self.last_kind, self.carry = "p", False

    def end_page(self):
        paras = self._container()["paragraphs"] if self.levels else []
        self.carry = self.last_kind == "p" and bool(paras) and ends_open(paras[-1]["raw"])

    # --- tách câu, làm sạch cho TTS, gán id ---
    def finalize(self):
        for lv1 in self.levels:
            for holder in [lv1, *lv1["chapters"]]:
                for p in holder["paragraphs"]:
                    p["sentences"] = [self._sentence(s) for s in split_sentences(p.pop("raw"))]
        notes = []
        for m in re.finditer(r"\[(\d+)\]\s*(.*?)(?=\[\d+\]\s|\Z)", " ".join(self.notes_raw), re.S):
            notes.append({"n": int(m.group(1)), "id": f"note{m.group(1)}",
                          "sentences": [self._sentence(s) for s in split_sentences(m.group(2).strip())]})
        return {"source_pdf": PDF.name, "levels": self.levels, "notes": notes,
                "stats": {"levels": len(self.levels),
                          "chapters": sum(len(l["chapters"]) for l in self.levels),
                          "paragraphs": self.n_para, "sentences": self.n_sent, "notes": len(notes)}}

    def _heading(self, raw):
        """Tiêu đề có thể chứa [n] ("Cậu bé xứ Calabria[5]") → tách riêng bản đọc."""
        return {"title": raw, "speech": speech_of(raw),
                "noterefs": [int(n) for n in NOTE_MARK.findall(raw)]}

    def _sentence(self, raw):
        self.n_sent += 1
        return {"id": f"s{self.n_sent:06d}", "raw": raw,
                "speech": speech_of(raw),
                "noterefs": [int(n) for n in NOTE_MARK.findall(raw)]}


def apply_speech_fixes(data):
    """Đọc sua_cach_doc.csv; dòng có cột speech → thay bản đọc của câu có id đó.
    id đánh tuần tự nên chỉ ổn định khi quy tắc tách câu không đổi: id không tìm thấy → dừng."""
    if not FIXES_CSV.exists():
        return
    import csv
    by_id = {}
    for lv in data["levels"]:
        for h in [lv, *lv["chapters"]]:
            by_id[h["id"]] = h              # tiêu đề tháng/truyện cũng sửa được bản đọc
            if h.get("dateline"):
                by_id[h["dateline"]["id"]] = h["dateline"]
            for p in h["paragraphs"]:
                for s in p["sentences"]:
                    by_id[s["id"]] = s
    for n in data["notes"]:
        for s in n["sentences"]:
            by_id[s["id"]] = s
    applied, unknown = 0, []
    with FIXES_CSV.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            sid = row["id"].strip()
            if sid not in by_id:
                unknown.append(sid)
            elif row.get("speech", "").strip():
                by_id[sid]["speech"] = row["speech"].strip()
                applied += 1
    if unknown:
        sys.exit(f"DỪNG: {FIXES_CSV.name} có id không tồn tại {unknown} — quy tắc tách câu đã đổi?")
    print(f"Sửa cách đọc: áp {applied} câu từ {FIXES_CSV.name}")


def main():
    doc = pymupdf.open(PDF)
    book = Book()
    in_notes = False
    for pno in range(FIRST_BODY_PAGE - 1, len(doc)):
        for block in doc[pno].get_text("dict")["blocks"]:
            for kind, text in block_runs(block):
                if kind == "note":               # vùng chú thích cuối sách
                    in_notes = True
                    book.notes_raw.append(text)
                elif in_notes:
                    print(f"CẢNH BÁO: dòng '{kind}' sau vùng chú thích, trang {pno+1}: {text[:60]}")
                elif kind == "h1":
                    book.add_h1(text)
                elif kind == "h2":
                    book.add_h2(text)
                elif kind == "het":
                    pass
                elif kind == "bolditalic" and book.last_kind in ("h2", "dateline"):
                    book.add_dateline(text)
                else:                            # body, hoặc bolditalic không sau h2 (đề từ Mở đầu)
                    book.add_paragraph(text)
        book.end_page()

    data = book.finalize()
    apply_speech_fixes(data)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    # --- đối chiếu với bookmark PDF: đây là tiêu chí "xong" của bước 1 ---
    toc_titles = [t[1].strip() for t in doc.get_toc()]
    got = [l["title"] for l in data["levels"]] + \
          [c["title"] for l in data["levels"] for c in l["chapters"]]
    got_clean = [NOTE_MARK.sub("", t).strip() for t in got]
    missing = sorted(set(toc_titles) - set(got_clean))
    extra = sorted(set(got_clean) - set(toc_titles))
    print("Thống kê:", data["stats"])
    print(f"Heading: bookmark={len(toc_titles)} trích được={len(got)}"
          f"  thiếu={missing or 'không'}  thừa={extra or 'không'}")
    no_date = [c["title"] for l in data["levels"] for c in l["chapters"] if not c["dateline"]]
    print("Truyện không có dòng ngày:", no_date or "không")
    refs = set()
    for l in data["levels"]:
        refs.update(l["noterefs"])
        for h in [l, *l["chapters"]]:
            refs.update(h.get("noterefs", []))
            if h.get("dateline"):
                refs.update(h["dateline"]["noterefs"])
            for p in h["paragraphs"]:
                for s in p["sentences"]:
                    refs.update(s["noterefs"])
    note_ids = {n["n"] for n in data["notes"]}
    print(f"noteref: {len(refs)} tham chiếu / {len(note_ids)} chú thích;"
          f" chú thích không được trỏ tới: {sorted(note_ids - refs) or 'không'};"
          f" tham chiếu không có chú thích: {sorted(refs - note_ids) or 'không'}")
    print("Ghi:", OUT.relative_to(ROOT))
    return 0 if not missing and not extra and refs == note_ids else 1


if __name__ == "__main__":
    sys.exit(main())
