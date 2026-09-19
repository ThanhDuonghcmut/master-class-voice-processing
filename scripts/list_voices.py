"""Sinh mẫu 3 câu cho cả 25 giọng VieNeu vào build/thu-giong/ để chọn giọng bằng tai.

Đổi giọng: sửa VOICE trong scripts/02_tts.py, xoá build/wav rồi chạy lại make tts.

    .venv/bin/python scripts/list_voices.py
"""
import os
import time

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

import numpy as np
import soundfile as sf
from vieneu import Vieneu

from book_units import BUILD

OUT = BUILD / "thu-giong"
TEXT = ["Hôm nay là ngày khai trường. Mấy tháng nghỉ hè của chúng tôi đã đi qua như một giấc mộng.",
        "Sáng nay, mẹ tôi dắt tôi đến phân hiệu Baretti để ghi tên tôi vào lớp ba.",
        "Thầy bảo tôi: “Chúng ta thế là xa nhau mãi rồi, phải không Enrico?”"]

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    tts = Vieneu()
    for i, (label, name) in enumerate(tts.list_preset_voices(), 1):
        t0 = time.time()
        audio = np.concatenate([tts.infer(s, voice=name) for s in TEXT])
        star = "sao_" if label.startswith("⭐") else ""
        sf.write(OUT / f"{i:02d}_{star}{name.replace(' ', '_')}.wav", audio, 48000)
        print(f"{i:02d} {label:58s} {len(audio)/48000:5.1f}s  RTF={(time.time()-t0)/(len(audio)/48000):.2f}")
    print("→", OUT)
