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
NOTES_GROUP = "notes"
NOTES_H1_ID = "notes-h1"
NOTES_TITLE = "Chú thích"

# Khoảng nghỉ (giây) chèn SAU mỗi loại đơn vị khi ghép mp3. Mỗi clip còn giữ 0,05 s im lặng
# thật ở hai đầu (03_concat_mp3.KEEP_MARGIN_S) nên khoảng nghe được = giá trị này + 0,1 s.
# Chuẩn đo 2026-09-19: cho VieNeu (Đức Trí) đọc liền 12 cặp câu → nó tự nghỉ giữa câu
# trung vị 0,71 s (0,52–0,89). 0,35 cũ nghe sát; 0,6 (=0,7 nghe được) người nghe vẫn thấy
# hơi nhanh → lấy mức trên của dải đo: 0,8 (=0,9 nghe được); các mốc khác nới theo tỷ lệ.
PAUSE_AFTER = {"front": 1.8, "h1": 2.2, "h2": 1.8, "dateline": 1.3, "sent": 0.8, "para_end": 1.4,
               "note_h1": 1.6, "note_sent": 0.8, "note_end": 1.1}


@dataclass
class Unit:
    group: str      # 1 nhóm = 1 file mp3 + 1 file smil (tháng-không-truyện, truyện, hoặc chú thích)
    id: str         # id phần tử trong dtbook.xml
    kind: str       # h1 | h2 | dateline | sent | note_h1 | note_sent
    text: str       # bản đọc (đã bỏ [n])
    para_end: bool = False   # câu cuối đoạn → nghỉ dài hơn


def load_metadata():
    return json.loads((ROOT / "metadata.json").read_text(encoding="utf-8"))


def load_book():
    return json.loads(BOOK_JSON.read_text(encoding="utf-8"))


def iter_units(book):
    meta = load_metadata()
    yield Unit(FRONT_GROUP, "doctitle", "front", meta["title"])
    yield Unit(FRONT_GROUP, "docauthor", "front", meta["creator"])
    for lv in book["levels"]:
        yield Unit(lv["id"], lv["id"], "h1", lv["speech"])
        yield from _paragraph_units(lv["id"], lv["paragraphs"], "sent")
        for ch in lv["chapters"]:
            yield Unit(ch["id"], ch["id"], "h2", ch["speech"])
            if ch["dateline"]:
                yield Unit(ch["id"], ch["dateline"]["id"], "dateline", ch["dateline"]["speech"])
            yield from _paragraph_units(ch["id"], ch["paragraphs"], "sent")
    yield Unit(NOTES_GROUP, NOTES_H1_ID, "note_h1", NOTES_TITLE)
    for note in book["notes"]:
        yield from _paragraph_units(NOTES_GROUP, [note], "note_sent")


def _paragraph_units(group, paragraphs, kind):
    for p in paragraphs:
        for i, s in enumerate(p["sentences"]):
            yield Unit(group, s["id"], kind, s["speech"], para_end=(i == len(p["sentences"]) - 1))


def groups_in_order(book):
    seen = []
    for u in iter_units(book):
        if not seen or seen[-1] != u.group:
            seen.append(u.group)
    return seen
