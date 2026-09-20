"""Dùng chung cho bước 2–5: duyệt book.json theo đúng THỨ TỰ ĐỌC, mỗi đơn vị = 1 <sent>/<h1>/<h2> = 1 clip audio.

Nếu thay đổi thứ tự hay thêm loại đơn vị, sửa ở đây — bốn bước sau tự khớp nhau.
"""
import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
BOOK_JSON = BUILD / "book.json"

FRONT_GROUP = "front"          # tên sách + tác giả, đọc trước tiên
NOTE_LABEL = "Chú thích:"      # đọc trước mỗi chú thích; không có "Hết chú thích" — khoảng nghỉ dài đủ làm ranh giới

# Khoảng nghỉ (giây) chèn SAU mỗi loại đơn vị khi ghép mp3. Mỗi clip còn giữ 0,05 s im lặng
# thật ở hai đầu (03_concat_mp3.KEEP_MARGIN_S) nên khoảng nghe được = giá trị này + 0,1 s.
# Chuẩn đo 2026-09-19: cho VieNeu (Đức Trí) đọc liền 12 cặp câu → nó tự nghỉ giữa câu
# trung vị 0,71 s (0,52–0,89). Lúc chọn 0,8 thì clip SMIL chưa bao khoảng nghỉ nên Thorium
# thực phát 0 s (cạm bẫy 8); sau khi sửa, trả về đúng số đo: 0,6 (=0,7 nghe được).
PAUSE_AFTER = {"front": 1.6, "h1": 1.9, "h2": 1.6, "dateline": 1.1, "sent": 0.6, "para_end": 1.1,
               "note_label": 0.3, "note_sent": 0.6, "note_end": 1.1}


@dataclass
class Unit:
    group: str      # 1 nhóm = 1 file mp3 + 1 file smil (tháng-không-truyện, truyện, hoặc chú thích)
    id: str         # id phần tử trong dtbook.xml
    kind: str       # h1 | h2 | dateline | sent | note_label | note_sent
    text: str       # bản đọc (đã bỏ [n])
    para_end: bool = False   # câu cuối đoạn → nghỉ dài hơn


def load_metadata():
    return json.loads((ROOT / "metadata.json").read_text(encoding="utf-8"))


def load_book():
    return json.loads(BOOK_JSON.read_text(encoding="utf-8"))


def iter_units(book):
    """Chú thích đọc NGAY SAU đoạn chứa [n] (chọn B trong 3 phương án, xem KE-HOACH.md);
    [n] nằm trong tiêu đề truyện → đọc sau dòng ngày (hoặc sau tiêu đề nếu không có dòng ngày)."""
    meta = load_metadata()
    notes = {n["n"]: n for n in book["notes"]}
    yield Unit(FRONT_GROUP, "doctitle", "front", meta["title"])
    yield Unit(FRONT_GROUP, "docauthor", "front", meta["creator"])
    for lv in book["levels"]:
        yield Unit(lv["id"], lv["id"], "h1", lv["speech"])
        yield from _note_units(lv["id"], lv["noterefs"], notes)
        yield from _paragraph_units(lv["id"], lv["paragraphs"], notes)
        for ch in lv["chapters"]:
            yield Unit(ch["id"], ch["id"], "h2", ch["speech"])
            refs = list(ch["noterefs"])
            if ch["dateline"]:
                yield Unit(ch["id"], ch["dateline"]["id"], "dateline", ch["dateline"]["speech"])
                refs += ch["dateline"]["noterefs"]
            yield from _note_units(ch["id"], refs, notes)
            yield from _paragraph_units(ch["id"], ch["paragraphs"], notes)


def _paragraph_units(group, paragraphs, notes):
    for p in paragraphs:
        for i, s in enumerate(p["sentences"]):
            yield Unit(group, s["id"], "sent", s["speech"], para_end=(i == len(p["sentences"]) - 1))
        yield from _note_units(group, [n for s in p["sentences"] for n in s["noterefs"]], notes)


def _note_units(group, refs, notes):
    for n in refs:
        note = notes[n]
        yield Unit(group, f"{note['id']}-label", "note_label", NOTE_LABEL)
        for i, s in enumerate(note["sentences"]):
            yield Unit(group, s["id"], "note_sent", s["speech"], para_end=(i == len(note["sentences"]) - 1))


def groups_in_order(book):
    seen = []
    for u in iter_units(book):
        if not seen or seen[-1] != u.group:
            seen.append(u.group)
    return seen
