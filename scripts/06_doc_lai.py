"""Đọc lại những câu TTS phát âm hỏng (lặp cụm từ, khựng) — chọn bản tốt nhất trong N lần.

VieNeu sinh audio bằng sampling nên thỉnh thoảng lặp một cụm ("đi đi, đi đi" thành ba lần).
Không có tham số nào chặn được (đã thử repetition_penalty 1.35/1.5 và temperature 0.5/0.3:
không nhất quán), nên cách làm là đọc N lần rồi chấm điểm từng bản:

  - Có faster-whisper: nghe ngược từng bản bằng ASR rồi so với văn bản gốc, chọn bản giống nhất.
    Đây là cách duy nhất phát hiện được lặp ở câu mà VĂN BẢN vốn đã có từ lặp ("đi đi, đi đi"),
    vì đọc thừa một lần chỉ dài thêm vài phần mười giây, không phân biệt được bằng thời lượng.
  - Không có: quay về so thời lượng với kỳ vọng (số ký tự × giây/ký tự đo trên cả sách).

Câu cần đọc lại lấy từ cột `doc_lai` trong sua_cach_doc.csv (điền "x"), hoặc truyền id trực tiếp.
Chỉ ghi đè khi bản mới GẦN KỲ VỌNG HƠN bản đang có; bản cũ lưu ở build/doc_lai_cu/ để so.
Xong thì cột doc_lai tự thành "xong-<ngày>" để lần chạy sau không đọc lại nữa — nghe vẫn chưa
ưng thì sửa lại thành "x" rồi chạy tiếp, mỗi lần sampling ra bản khác.

    .venv/bin/python scripts/06_doc_lai.py                 # mọi id có doc_lai="x"
    .venv/bin/python scripts/06_doc_lai.py s004387 s003622 # id cụ thể
    .venv/bin/python scripts/06_doc_lai.py --lan 8 s004387 # đọc 8 lần thay vì 5
"""
import csv
import os
import shutil
import sys

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

import numpy as np
import soundfile as sf

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from book_units import BUILD, ROOT, iter_units, load_book

_asr = None


def nghe_nguoc(path):
    """Trả về văn bản ASR nghe được từ file wav, hoặc None nếu không có faster-whisper."""
    global _asr
    if _asr is None:
        try:
            from faster_whisper import WhisperModel
            _asr = WhisperModel(ASR_MODEL, device="cpu", compute_type="int8")
        except Exception as e:
            print(f"(không dùng được ASR: {e}; chấm điểm bằng thời lượng)")
            _asr = False
    if not _asr:
        return None
    segs, _info = _asr.transcribe(str(path), language="vi", beam_size=5)
    return " ".join(s.text.strip() for s in segs)


def giong_nhau(a, b):
    """Độ giống giữa ASR và văn bản gốc, bỏ dấu câu và chữ hoa."""
    import re
    from difflib import SequenceMatcher
    chuan = lambda t: re.sub(r"[^\w\s]", " ", t.lower())
    chuan = lambda t, _c=chuan: " ".join(_c(t).split())
    return SequenceMatcher(None, chuan(a), chuan(b)).ratio()

WAV_DIR, BACKUP = BUILD / "wav", BUILD / "doc_lai_cu"
TAM = BUILD / "_doc_lai_tam.wav"
FIXES_CSV = ROOT / "sua_cach_doc.csv"
VOICE = "Đức Trí"
SR = 48_000
SEC_PER_CHAR = 0.081     # đo trên cả sách: 439k ký tự → 9,4 h giọng đọc
LAN_MAC_DINH = 5
ASR_MODEL = "small"      # tiny/base nghe sai nhiều ở tiếng Việt; small đủ để đếm cụm lặp
DU_TOT = 0.93            # bản hiện tại khớp ASR tới mức này thì khỏi đọc lại


def ids_from_csv():
    if not FIXES_CSV.exists():
        return []
    with FIXES_CSV.open(encoding="utf-8-sig") as f:
        return [r["id"].strip() for r in csv.DictReader(f) if r.get("doc_lai", "").strip() == "x"]


def mark_done(ids):
    """doc_lai: "x" → "xong-<ngày>" cho những id vừa xử lý."""
    if not FIXES_CSV.exists():
        return
    from datetime import date
    with FIXES_CSV.open(encoding="utf-8-sig") as f:
        rows, fields = list(csv.DictReader(f)), None
        f.seek(0)
        fields = next(csv.reader(f))
    for r in rows:
        if r["id"].strip() in ids and r.get("doc_lai") == "x":
            r["doc_lai"] = f"xong-{date.today()}"
    with FIXES_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main(argv):
    lan = LAN_MAC_DINH
    if "--lan" in argv:
        i = argv.index("--lan")
        lan = int(argv[i + 1])
        del argv[i:i + 2]
    ids = argv or ids_from_csv()
    if not ids:
        sys.exit('Không có id nào. Điền cột doc_lai="x" trong sua_cach_doc.csv, hoặc truyền id.')

    units = {u.id: u for u in iter_units(load_book())}
    from vieneu import Vieneu
    tts = Vieneu()
    BACKUP.mkdir(parents=True, exist_ok=True)
    for sid in ids:
        u = units.get(sid)
        if not u:
            print(f"{sid}: KHÔNG CÓ trong sách — bỏ qua")
            continue
        wav = WAV_DIR / u.group / f"{sid}.wav"
        cu = sf.info(wav).duration if wav.exists() else 0
        expect = len(u.text) * SEC_PER_CHAR
        # Chấm điểm bản đang có trước: đủ tốt thì khỏi đọc lại
        nghe_cu = nghe_nguoc(wav) if wav.exists() else None
        if nghe_cu is not None:
            diem_cu = giong_nhau(nghe_cu, u.text)
            if diem_cu >= DU_TOT:
                print(f"{sid} [{u.group}] bản hiện tại đã khớp ASR {diem_cu:.2f} — giữ nguyên")
                print(f"   nghe ra: {nghe_cu[:95]}")
                continue
        else:
            diem_cu = -abs(cu - expect)          # không có ASR: điểm = âm sai lệch thời lượng

        lan_doc = [tts.infer(u.text, voice=VOICE) for _ in range(lan)]
        durs = [len(a) / SR for a in lan_doc]
        diem = []
        for i, a in enumerate(lan_doc):
            sf.write(TAM, np.asarray(a, dtype=np.float32), SR, subtype="PCM_16")
            nghe = nghe_nguoc(TAM)
            diem.append(giong_nhau(nghe, u.text) if nghe is not None else -abs(durs[i] - expect))
        best = max(range(lan), key=lambda i: diem[i])
        if wav.exists() and diem_cu >= diem[best]:
            print(f"{sid} [{u.group}] giữ bản cũ (điểm {diem_cu:.2f} ≥ tốt nhất trong {lan} lần "
                  f"{diem[best]:.2f})")
            continue
        if wav.exists():
            shutil.copy(wav, BACKUP / f"{sid}.wav")
        wav.parent.mkdir(parents=True, exist_ok=True)
        sf.write(wav, np.asarray(lan_doc[best], dtype=np.float32), SR, subtype="PCM_16")
        wav.with_suffix(".txt").write_text(u.text, encoding="utf-8")
        print(f"{sid} [{u.group}] cũ {cu:5.1f}s (điểm {diem_cu:.2f}) → mới {durs[best]:5.1f}s "
              f"(điểm {diem[best]:.2f}; {lan} lần: {', '.join('%.2f' % x for x in diem)})")
        print(f"   {u.text[:95]}")
    if not argv:
        mark_done(set(ids))
    print(f"\nBản cũ giữ ở {BACKUP.relative_to(ROOT)}/ để so. Tiếp: 03_concat_mp3.py rồi 04_build_daisy.py")


if __name__ == "__main__":
    main(sys.argv[1:])
