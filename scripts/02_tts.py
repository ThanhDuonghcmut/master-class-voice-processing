"""Bước 2: build/book.json → build/wav/<nhóm>/<id>.wav — một file WAV cho MỖI đơn vị đọc.

Đơn vị đọc = mọi thứ sẽ thành <sent> trong DTBook: tiêu đề cấp 1/2, dòng ngày, câu, câu chú thích.
Mỗi câu một file để bước 3 đo độ dài chính xác → clipBegin/clipEnd không cần forced alignment.

Chạy lại được: file .wav đã có thì bỏ qua. Xoá file nào muốn đọc lại rồi chạy lại.

    .venv/bin/python scripts/02_tts.py                 # cả sách (~1,5 h trên M5 Pro)
    .venv/bin/python scripts/02_tts.py lv1-02 lv2-001  # chỉ vài nhóm (dựng thử)
"""
import json
import os
import sys
import time

# Phải đặt TRƯỚC khi import vieneu: onnxruntime ≥1.30 từ chối file .data qua symlink của HF cache
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

import numpy as np
import soundfile as sf
from vieneu import Vieneu

from book_units import BUILD, iter_units, load_book

WAV_DIR = BUILD / "wav"
LOG = BUILD / "tts_log.jsonl"

VOICE = "Đức Trí"        # nam · Nam · đọc truyện — người dùng chọn sau khi nghe 25 mẫu
SAMPLE_RATE = 48_000
# Câu đọc chậm hơn mức này (giây/ký tự) nghi là lảm nhảm → ghi cảnh báo để QA nghe lại
SLOW_SEC_PER_CHAR = 0.15


def main(only):
    book = load_book()
    todo = [(u.group, u.id, u.text) for u in iter_units(book)
            if (not only or u.group in only) and not (WAV_DIR / u.group / f"{u.id}.wav").exists()]
    total = sum(1 for _ in iter_units(book))
    print(f"Đơn vị đọc: {total} tổng, {len(todo)} cần sinh, giọng {VOICE}")
    if not todo:
        return
    tts = Vieneu()
    t_start, audio_sec = time.time(), 0.0
    with LOG.open("a", encoding="utf-8") as log:
        for k, (group, uid, text) in enumerate(todo, 1):
            t0 = time.time()
            audio = tts.infer(text, voice=VOICE)
            dur = len(audio) / SAMPLE_RATE
            out = WAV_DIR / group / f"{uid}.wav"
            out.parent.mkdir(parents=True, exist_ok=True)
            sf.write(out, np.asarray(audio, dtype=np.float32), SAMPLE_RATE, subtype="PCM_16")
            rec = {"group": group, "id": uid, "chars": len(text), "sec": round(dur, 3),
                   "compute": round(time.time() - t0, 3)}
            if dur / max(len(text), 1) > SLOW_SEC_PER_CHAR:
                rec["warn"] = "chậm bất thường, nghe lại"
            log.write(json.dumps(rec, ensure_ascii=False) + "\n")
            audio_sec += dur
            if k % 50 == 0 or k == len(todo):
                el = time.time() - t_start
                print(f"  {k}/{len(todo)}  audio {audio_sec/60:.1f} phút  "
                      f"máy {el/60:.1f} phút  RTF {el/audio_sec:.2f}  còn ~{el/k*(len(todo)-k)/60:.0f} phút")


if __name__ == "__main__":
    main(set(sys.argv[1:]))
