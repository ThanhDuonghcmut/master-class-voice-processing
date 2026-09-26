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

from asr_kiem import dau_hieu, giong_nhau, nghe_nguoc

WAV_DIR, BACKUP = BUILD / "wav", BUILD / "doc_lai_cu"
TAM = BUILD / "_doc_lai_tam.wav"
FIXES_CSV = ROOT / "sua_cach_doc.csv"
VOICE = "Đức Trí"
SR = 48_000
SEC_PER_CHAR = 0.081     # đo trên cả sách: 439k ký tự → 9,4 h giọng đọc
LAN_MAC_DINH = 5
DU_TOT = 0.93            # điểm giống tối thiểu để coi là đạt (kèm điều kiện không có dấu hiệu lặp)


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
            diem_cu, co_loi_cu = giong_nhau(nghe_cu, u.text), dau_hieu(u.text, nghe_cu)
            if diem_cu >= DU_TOT and not co_loi_cu:
                print(f"{sid} [{u.group}] bản hiện tại đạt (điểm {diem_cu:.2f}, không thấy lặp/thiếu)")
                print(f"   nghe ra: {nghe_cu[:95]}")
                continue
            if co_loi_cu:
                print(f"{sid} [{u.group}] bản hiện tại: {co_loi_cu} (điểm {diem_cu:.2f}) — đọc lại")
        else:
            diem_cu, co_loi_cu = -abs(cu - expect), ""   # không có ASR: chấm bằng sai lệch thời lượng

        lan_doc = [tts.infer(u.text, voice=VOICE) for _ in range(lan)]
        durs = [len(a) / SR for a in lan_doc]
        diem, co_loi = [], []
        for i, a in enumerate(lan_doc):
            sf.write(TAM, np.asarray(a, dtype=np.float32), SR, subtype="PCM_16")
            nghe = nghe_nguoc(TAM) if nghe_cu is not None else None
            diem.append(giong_nhau(nghe, u.text) if nghe is not None else -abs(durs[i] - expect))
            co_loi.append(dau_hieu(u.text, nghe) if nghe is not None else "")
        # ưu tiên bản KHÔNG có dấu hiệu lặp/thiếu, trong đó chọn bản điểm cao nhất
        best = max(range(lan), key=lambda i: (not co_loi[i], diem[i]))
        tot_hon = (not co_loi[best], diem[best]) > (not co_loi_cu, diem_cu)
        if wav.exists() and not tot_hon:
            print(f"{sid} [{u.group}] giữ bản cũ ({lan} lần đọc lại không bản nào tốt hơn: "
                  f"điểm tốt nhất {diem[best]:.2f}{', vẫn ' + co_loi[best] if co_loi[best] else ''})")
            continue
        if wav.exists():
            shutil.copy(wav, BACKUP / f"{sid}.wav")
        wav.parent.mkdir(parents=True, exist_ok=True)
        sf.write(wav, np.asarray(lan_doc[best], dtype=np.float32), SR, subtype="PCM_16")
        wav.with_suffix(".txt").write_text(u.text, encoding="utf-8")
        print(f"{sid} [{u.group}] cũ {cu:5.1f}s (điểm {diem_cu:.2f}{', ' + co_loi_cu if co_loi_cu else ''}) "
              f"→ mới {durs[best]:5.1f}s (điểm {diem[best]:.2f}; {lan} lần: "
              f"{', '.join('%.2f' % x for x in diem)})")
        print(f"   {u.text[:95]}")
    if not argv:
        mark_done(set(ids))
    print(f"\nBản cũ giữ ở {BACKUP.relative_to(ROOT)}/ để so. Tiếp: 03_concat_mp3.py rồi 04_build_daisy.py")


if __name__ == "__main__":
    main(sys.argv[1:])
