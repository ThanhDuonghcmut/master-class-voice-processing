"""Dùng chung cho bước 06 (đọc lại câu hỏng) và 07 (quét cả sách): nghe ngược bản TTS bằng ASR
rồi so với văn bản gốc.

Hai chỉ số:
  - điểm giống: tỉ lệ khớp chuỗi, dùng để chọn bản đọc tốt hơn.
  - dấu hiệu: "lặp cụm N từ" / "thiếu X% số từ" — bắt được lỗi mà điểm giống bỏ sót, vì ở câu dài
    một cụm lặp chỉ kéo điểm xuống vài phần trăm (0,94 vẫn đang lặp).
"""
import re
import unicodedata
from pathlib import Path
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


def nghe_nguoc(path, moc_tu=False):
    """Trả văn bản ASR; moc_tu=True thì trả thêm [(từ, giây bắt đầu, giây kết thúc), …].
    Bật mốc từ làm ASR chậm thêm khoảng 25%, nhưng có mốc mới dò được ngắt nhịp sai."""
    segs, _ = nap_mo_hinh().transcribe(str(path), language="vi", beam_size=5, word_timestamps=moc_tu)
    segs = list(segs)
    text = " ".join(s.text.strip() for s in segs)
    if not moc_tu:
        return text
    return text, [(w.word.strip(), round(w.start, 3), round(w.end, 3))
                  for s in segs for w in (s.words or [])]


def ngat_nhip(text, moc, nghi_min=0.45, boi=1.8):
    """KHÔNG DÙNG để báo lỗi — giữ lại vì kết quả vẫn ghi ra file cho ai muốn xem.

    Ý định ban đầu: dò chỗ ngắt sai bằng cách tìm nghỉ dài ở chỗ không có dấu câu
    ("Thầy giáo | mới ngay từ sáng"). Kiểm bằng tai trên ba chỗ bị báo nặng nhất thì hỏng cả ba:
      - Chỗ báo "nghỉ 1,16 giây" thực tế KHÔNG có khoảng nghỉ nào. Mốc thời gian của Whisper là
        ước lượng theo attention, không phải đo thật, nên lệch hàng trăm mili giây quanh tên riêng
        và số — đúng những chỗ hay bị báo.
      - Hai chỗ còn lại nghỉ đúng ngữ pháp: tiếng Việt ngắt được sau "rằng", sau mệnh đề phụ,
        những chỗ không hề có dấu câu.
    Muốn làm đúng thì cần mốc thời gian từ forced alignment (dóng hàng âm với văn bản gốc), không
    phải từ ASR, và cần luật ngắt nhịp tiếng Việt chứ không chỉ dựa vào dấu câu.

    Hai điều đã học khi hiệu chỉnh:
      - Không xét "đọc liền qua dấu phẩy": tiếng Việt đọc liền qua dấu phẩy là bình thường,
        tiêu chí này báo tới 30% số câu.
      - Không dùng ngưỡng tuyệt đối: câu dài nào cũng có nhịp lấy hơi 0,3-0,4 giây. Chỉ báo khi
        khoảng nghỉ vượt nghi_min VÀ dài hơn `boi` lần trung vị các khoảng nghỉ của chính câu đó.
    Cần dóng hàng từ ASR với từ gốc vì ASR nghe sai một số từ."""
    from difflib import SequenceMatcher
    goc_tu = re.findall(r"\S+", text)
    co_dau = [bool(re.search(r"[,;:.!?…]$", w.strip("”\"’»)"))) for w in goc_tu]
    a = [chuan(w[0]) for w in moc]
    b = [chuan(w) for w in goc_tu]
    anh_xa = {}
    for kh in SequenceMatcher(None, a, b).get_matching_blocks():
        for k in range(kh.size):
            anh_xa[kh.a + k] = kh.b + k
    khoang = [moc[i + 1][1] - moc[i][2] for i in range(len(moc) - 1)]
    if len(khoang) < 4:
        return []
    import statistics
    nen = max(statistics.median(khoang), 0.12)      # nhịp nghỉ nền của chính câu này
    ra = []
    for i, k in enumerate(khoang):
        j = anh_xa.get(i)
        if j is None or j >= len(co_dau) or co_dau[j]:
            continue
        if k >= nghi_min and k >= nen * boi:
            ra.append(f"nghỉ {k:.2f}s sau “{goc_tu[j]}” (chỗ này không có dấu câu)")
    return ra


# ASR viết số bằng chữ số ("thứ 5", "2 cấp") còn sách viết bằng chữ ("thứ năm", "hai cấp");
# quy về một dạng để khỏi báo lỗi giả.
SO = {"không": "0", "một": "1", "mốt": "1", "hai": "2", "ba": "3", "bốn": "4", "tư": "4",
      "năm": "5", "lăm": "5", "sáu": "6", "bảy": "7", "tám": "8", "chín": "9", "mười": "10",
      "giờ": "h", "mét": "m", "ki-lô-mét": "km"}   # ASR viết tắt đơn vị: "năm giờ" thành "5h"


def chuan(t):
    t = " ".join(re.sub(r"[^\w\s]", " ", t.lower()).split())
    t = " ".join(SO.get(w, w) for w in t.split())
    return re.sub(r"\b(\d+) (h|m|km)\b", r"\1\2", t)   # "5 h" và "5h" là một


def bo_so(tu):
    """Bỏ mọi token số — ASR viết "hai mươi bảy" thành "27", đếm từ sẽ lệch dù đọc đúng."""
    return [w for w in tu if not re.fullmatch(r"[\d.,]+(h|m|km)?|mươi|trăm|nghìn|ngàn|triệu|tỷ", w)]


def _tu_dien_am_tiet():
    global _AM_TIET
    try:
        return _AM_TIET
    except NameError:
        f = Path(__file__).with_name("data") / "am_tiet_tieng_viet.txt"
        _AM_TIET = {l.strip().lower() for l in f.open(encoding="utf-8-sig") if l.strip()} if f.exists() else set()
        return _AM_TIET


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


def ten_rieng(text):
    """Tên riêng và từ nước ngoài: viết hoa giữa câu, hoặc không phải âm tiết tiếng Việt
    (senor, nonna, capataz) — ASR nghe những từ này thành hai tiếng rời nên hay báo lặp giả."""
    ten = {m.group(1).lower() for m in re.finditer(r"(?<!^)(?<![.!?“\"…]\s)\b([A-ZÀ-ỸĐ][\wà-ỹ]+)", text)}
    am = _tu_dien_am_tiet()
    if am:
        ten |= {w for w in chuan(text).split() if w.isalpha() and w not in am}
    return ten


def lap_do_tach_ten(text, nghe, cum):
    """True nếu cụm lặp trong bản ASR thực ra là một TÊN RIÊNG bị ASR tách làm hai từ giống nhau
    ("Giorgio" nghe thành "gio gio", "senor" thành "xe nơ", "xổ số" thành "số số").
    Nhận ra bằng cách: ngay chỗ đó văn bản gốc có một từ chứa cụm ấy, hoặc là tên riêng."""
    ten = ten_rieng(text)
    goc = chuan(text).split()
    c = cum.split()[0]
    for w in goc:
        if w in ten and (c in w or w.startswith(c[:2])):
            return True
    return False


def cum_lap_dau(tu, n):
    """Cụm n từ đầu tiên bị lặp liên tiếp, để ghi rõ máy nghi cụm nào."""
    for i in range(len(tu) - 2 * n + 1):
        if tu[i:i + n] == tu[i + n:i + 2 * n]:
            return " ".join(tu[i:i + n])
    return ""


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
            cum = cum_lap_dau(a, n)
            if n == 1 and cum and lap_do_tach_ten(text, nghe, cum):
                continue          # ASR tách tên riêng, không phải TTS đọc lặp
            return f"lặp cụm {n} từ" + (f" “{cum}”" if cum else "")
    ti = len(bo_so(a)) / max(len(bo_so(b)), 1)
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


def ten_rieng(text):
    """Tên riêng và từ nước ngoài: viết hoa giữa câu, hoặc không phải âm tiết tiếng Việt
    (senor, nonna, capataz) — ASR nghe những từ này thành hai tiếng rời nên hay báo lặp giả."""
    ten = {m.group(1).lower() for m in re.finditer(r"(?<!^)(?<![.!?“\"…]\s)\b([A-ZÀ-ỸĐ][\wà-ỹ]+)", text)}
    am = _tu_dien_am_tiet()
    if am:
        ten |= {w for w in chuan(text).split() if w.isalpha() and w not in am}
    return ten


def lap_do_tach_ten(text, nghe, cum):
    """True nếu cụm lặp trong bản ASR thực ra là một TÊN RIÊNG bị ASR tách làm hai từ giống nhau
    ("Giorgio" nghe thành "gio gio", "senor" thành "xe nơ", "xổ số" thành "số số").
    Nhận ra bằng cách: ngay chỗ đó văn bản gốc có một từ chứa cụm ấy, hoặc là tên riêng."""
    ten = ten_rieng(text)
    goc = chuan(text).split()
    c = cum.split()[0]
    for w in goc:
        if w in ten and (c in w or w.startswith(c[:2])):
            return True
    return False


def cum_lap_dau(tu, n):
    """Cụm n từ đầu tiên bị lặp liên tiếp, để ghi rõ máy nghi cụm nào."""
    for i in range(len(tu) - 2 * n + 1):
        if tu[i:i + n] == tu[i + n:i + 2 * n]:
            return " ".join(tu[i:i + n])
    return ""


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
            cum = cum_lap_dau(a, n)
            if n == 1 and cum and lap_do_tach_ten(text, nghe, cum):
                continue          # ASR tách tên riêng, không phải TTS đọc lặp
            return f"lặp cụm {n} từ" + (f" “{cum}”" if cum else "")
    ti = len(bo_so(a)) / max(len(bo_so(b)), 1)
    if ti < 0.85:
        return f"thiếu {(1 - ti) * 100:.0f}% số từ"
    return ""


