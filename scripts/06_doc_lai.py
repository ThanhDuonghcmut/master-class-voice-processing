"""Đọc lại những câu TTS phát âm hỏng (lặp cụm từ, khựng) — chọn bản tốt nhất trong N lần.

VieNeu sinh audio bằng sampling nên thỉnh thoảng lặp một cụm ("đi đi, đi đi" thành ba lần).
Không có tham số nào chặn được (đã thử repetition_penalty 1.35/1.5 và temperature 0.5/0.3:
không nhất quán), nhưng bản lặp thừa LUÔN dài hơn bản đúng → đọc N lần rồi chọn bản có thời
lượng gần kỳ vọng nhất (kỳ vọng = số ký tự × giây/ký tự đo trên cả sách).

Câu cần đọc lại lấy từ cột `doc_lai` trong sua_cach_doc.csv (điền "x"), hoặc truyền id trực tiếp.
Bản cũ lưu ở build/doc_lai_cu/ để so; nghe không ưng thì chạy lại, mỗi lần ra bản khác.

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

WAV_DIR, BACKUP = BUILD / "wav", BUILD / "doc_lai_cu"
FIXES_CSV = ROOT / "sua_cach_doc.csv"
VOICE = "Đức Trí"
SR = 48_000
SEC_PER_CHAR = 0.081     # đo trên cả sách: 439k ký tự → 9,4 h giọng đọc
LAN_MAC_DINH = 5


def ids_from_csv():
    if not FIXES_CSV.exists():
        return []
    with FIXES_CSV.open(encoding="utf-8-sig") as f:
        return [r["id"].strip() for r in csv.DictReader(f) if r.get("doc_lai", "").strip()]


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
        lan_doc = [tts.infer(u.text, voice=VOICE) for _ in range(lan)]
        durs = [len(a) / SR for a in lan_doc]
        best = min(range(lan), key=lambda i: abs(durs[i] - expect))
        if wav.exists():
            shutil.copy(wav, BACKUP / f"{sid}.wav")
        wav.parent.mkdir(parents=True, exist_ok=True)
        sf.write(wav, np.asarray(lan_doc[best], dtype=np.float32), SR, subtype="PCM_16")
        wav.with_suffix(".txt").write_text(u.text, encoding="utf-8")
        print(f"{sid} [{u.group}] cũ {cu:5.1f}s → mới {durs[best]:5.1f}s (kỳ vọng {expect:5.1f}s; "
              f"{lan} lần: {', '.join('%.1f' % d for d in durs)})")
        print(f"   {u.text[:95]}")
    print(f"\nBản cũ giữ ở {BACKUP.relative_to(ROOT)}/ để so. Tiếp: 03_concat_mp3.py rồi 04_build_daisy.py")


if __name__ == "__main__":
    main(sys.argv[1:])
