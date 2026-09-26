"""Dùng chung cho bước 06 (đọc lại câu hỏng) và 07 (quét cả sách): nghe ngược bản TTS bằng ASR
rồi so với văn bản gốc.

Hai chỉ số:
  - điểm giống: tỉ lệ khớp chuỗi, dùng để chọn bản đọc tốt hơn.
  - dấu hiệu: "lặp cụm N từ" / "thiếu X% số từ" — bắt được lỗi mà điểm giống bỏ sót, vì ở câu dài
    một cụm lặp chỉ kéo điểm xuống vài phần trăm (0,94 vẫn đang lặp).
"""
import re
import unicodedata
from difflib import SequenceMatcher

ASR_MODEL = "small"      # tiny/base nghe sai nhiều ở tiếng Việt
LUONG_CPU = 2            # luồng CPU mỗi tiến trình

_asr = None


def nap_mo_hinh():
    global _asr
    if _asr is None:
        from faster_whisper import WhisperModel
        _asr = WhisperModel(ASR_MODEL, device="cpu", compute_type="int8", cpu_threads=LUONG_CPU)
    return _asr


def nghe_nguoc(path):
    segs, _ = nap_mo_hinh().transcribe(str(path), language="vi", beam_size=5)
    return " ".join(s.text.strip() for s in segs)


# ASR viết số bằng chữ số ("thứ 5", "2 cấp") còn sách viết bằng chữ ("thứ năm", "hai cấp");
# quy về một dạng để khỏi báo lỗi giả.
SO = {"không": "0", "một": "1", "mốt": "1", "hai": "2", "ba": "3", "bốn": "4", "tư": "4",
      "năm": "5", "lăm": "5", "sáu": "6", "bảy": "7", "tám": "8", "chín": "9", "mười": "10"}


def chuan(t):
    t = " ".join(re.sub(r"[^\w\s]", " ", t.lower()).split())
    return " ".join(SO.get(w, w) for w in t.split())


def so_lan_lap(tu, n):
    """Số lần một cụm n từ lặp lại NGAY SAU chính nó (đi đi / đi đi / đi đi)."""
    dem = 0
    for i in range(len(tu) - 2 * n + 1):
        if tu[i:i + n] == tu[i + n:i + 2 * n]:
            dem += 1
    return dem


def bo_thanh(w):
    import unicodedata
    d = unicodedata.normalize("NFD", w)
    return unicodedata.normalize("NFC", "".join(c for c in d if c not in "\u0300\u0301\u0303\u0309\u0323"))


def dau_hieu(text, nghe):
    """Dấu hiệu lỗi đọc, không phụ thuộc việc ASR nghe sai tên riêng:
    - "lặp": trong bản đọc có cụm lặp liên tiếp nhiều hơn trong văn bản gốc
    - "thiếu": bản đọc ngắn hơn văn bản gốc đáng kể
    Đếm trên dạng đã bỏ dấu thanh, vì ASR hay nghe từ láy thành từ lặp ("chầm chậm" thành
    "chậm chậm"); bỏ dấu thì cả hai đều là một cặp giống nhau nên không báo nhầm.
    Trả về chuỗi rỗng nếu không thấy dấu hiệu nào."""
    a = [bo_thanh(w) for w in chuan(nghe).split()]
    b = [bo_thanh(w) for w in chuan(text).split()]
    for n in (1, 2, 3, 4):
        if so_lan_lap(a, n) > so_lan_lap(b, n):
            return f"lặp cụm {n} từ"
    ti = len(a) / max(len(b), 1)
    if ti < 0.85:
        return f"thiếu {(1 - ti) * 100:.0f}% số từ"
    return ""



def bo_thanh(w):
    d = unicodedata.normalize("NFD", w)
    return unicodedata.normalize("NFC", "".join(c for c in d if c not in "\u0300\u0301\u0303\u0309\u0323"))


def giong_nhau(nghe, text):
    return SequenceMatcher(None, chuan(nghe), chuan(text)).ratio()


def so_lan_lap(tu, n):
    """Số lần một cụm n từ lặp lại NGAY SAU chính nó (đi đi / đi đi / đi đi)."""
    dem = 0
    for i in range(len(tu) - 2 * n + 1):
        if tu[i:i + n] == tu[i + n:i + 2 * n]:
            dem += 1
    return dem


def dau_hieu(text, nghe):
    """Dấu hiệu lỗi đọc, không phụ thuộc việc ASR nghe sai tên riêng:
    - "lặp": trong bản đọc có cụm lặp liên tiếp nhiều hơn trong văn bản gốc
    - "thiếu": bản đọc ngắn hơn văn bản gốc đáng kể
    Đếm trên dạng đã bỏ dấu thanh, vì ASR hay nghe từ láy thành từ lặp ("chầm chậm" thành
    "chậm chậm"); bỏ dấu thì cả hai đều là một cặp giống nhau nên không báo nhầm.
    Trả về chuỗi rỗng nếu không thấy dấu hiệu nào."""
    a = [bo_thanh(w) for w in chuan(nghe).split()]
    b = [bo_thanh(w) for w in chuan(text).split()]
    for n in (1, 2, 3, 4):
        if so_lan_lap(a, n) > so_lan_lap(b, n):
            return f"lặp cụm {n} từ"
    ti = len(a) / max(len(b), 1)
    if ti < 0.85:
        return f"thiếu {(1 - ti) * 100:.0f}% số từ"
    return ""


