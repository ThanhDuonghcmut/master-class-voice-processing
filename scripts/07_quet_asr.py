"""Quét ASR để tự tìm câu đọc sai — nghe ngược từng câu rồi so với văn bản gốc.

Bổ sung cho việc nghe thủ công: máy quét được cả sách, còn tai người thì bắt được những lỗi
máy không thấy (ngắt nhịp gượng, giọng đơ). Điểm thấp không chắc chắn là lỗi TTS — ASR cũng
nghe sai, nhất là tên riêng nước ngoài và câu dài — nên kết quả là DANH SÁCH NGHI VẤN để
người nghe kiểm lại, không phải kết luận.

    .venv/bin/python scripts/07_quet_asr.py --phan 3         # quét phần 3 (chia như trang QA)
    .venv/bin/python scripts/07_quet_asr.py lv2-069 lv2-070  # quét vài truyện
    .venv/bin/python scripts/07_quet_asr.py --phan 3 --tho 5 # 5 tiến trình song song

Kết quả: build/asr_quet.csv (mọi câu, kèm điểm và bản ASR nghe được) và bản tóm tắt in ra màn hình.
"""
import csv
import json
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from asr_kiem import dau_hieu, giong_nhau, nghe_nguoc
from book_units import BUILD, ROOT, groups_in_order, iter_units, load_book

OUT = BUILD / "asr_quet.csv"
NGUONG = 0.90        # dưới mức này thì đưa vào danh sách nghi vấn
# Mỗi tiến trình nạp một bản mô hình (khoảng 0,5 GB RAM). Đã thử cách nạp một bản rồi chia cho
# nhiều luồng qua num_workers của ctranslate2: chậm hơn 5 lần (0,3 câu/giây so với 1,8), vì phần
# tiền xử lý của faster-whisper chạy trong Python nên bị GIL chặn, num_workers chỉ giúp phần C++.
THO_MAC_DINH = 8     # số tiến trình chạy song song

def cham_diem(viec):
    """(id, nhóm, văn bản, đường dẫn wav) thành (id, nhóm, văn bản, ASR nghe ra, điểm)."""
    sid, group, text, wav = viec
    nghe = nghe_nguoc(wav)
    return sid, group, text, nghe, giong_nhau(nghe, text)


def chon_nhom(book, argv):
    """--phan N: chia sách làm 3 phần theo thời lượng như trang QA; hoặc liệt kê id nhóm."""
    timing = json.loads((BUILD / "timing.json").read_text(encoding="utf-8"))
    order = [g for g in groups_in_order(book) if g in timing]
    if "--phan" not in argv:
        return [g for g in argv if not g.startswith("--")] or order
    n = int(argv[argv.index("--phan") + 1])
    tong = sum(timing[g]["duration"] for g in order)
    phan, acc = [], 0.0
    for g in order:
        if len(phan) < 3 and acc + timing[g]["duration"] / 2 > tong / 3 * len(phan) and g != "front":
            phan.append([])
        if not phan:
            phan.append([])
        phan[-1].append(g)
        acc += timing[g]["duration"]
    return phan[n - 1]


def main(argv):
    tho = int(argv[argv.index("--tho") + 1]) if "--tho" in argv else THO_MAC_DINH
    book = load_book()
    nhom = set(chon_nhom(book, argv))
    ten = {lv["id"]: lv["speech"] for lv in book["levels"]}
    ten.update({c["id"]: c["speech"] for lv in book["levels"] for c in lv["chapters"]})
    viec = [(u.id, u.group, u.text, str(BUILD / "wav" / u.group / f"{u.id}.wav"))
            for u in iter_units(book)
            if u.group in nhom and (BUILD / "wav" / u.group / f"{u.id}.wav").exists()]
    print(f"Quét {len(viec)} câu thuộc {len(nhom)} nhóm, {tho} tiến trình song song…")
    t0 = time.time()
    ket_qua = []
    with ProcessPoolExecutor(max_workers=tho) as ex:
        for i, r in enumerate(ex.map(cham_diem, viec, chunksize=4), 1):
            ket_qua.append(r)
            if i % 50 == 0:
                el = time.time() - t0
                print(f"  {i}/{len(viec)}  {el/60:.1f} phút, còn khoảng {el/i*(len(viec)-i)/60:.0f} phút",
                      flush=True)
    ket_qua.sort(key=lambda r: r[4])
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "nhom", "truyen", "diem", "dau_hieu", "van_ban", "asr_nghe_ra"])
        for sid, g, text, nghe, diem in ket_qua:
            w.writerow([sid, g, ten.get(g, g), f"{diem:.3f}", dau_hieu(text, nghe), text, nghe])
    NGAN = 25   # câu quá ngắn (dòng ngày, nhãn "Chú thích:") điểm dao động mạnh, nhiều báo giả
    nghi = [r for r in ket_qua if dau_hieu(r[2], r[3]) and len(r[2]) >= NGAN]
    print(f"\nXong trong {(time.time()-t0)/60:.0f} phút. Điểm giống trung bình "
          f"{sum(r[4] for r in ket_qua)/len(ket_qua):.3f}; {len(nghi)} câu có dấu hiệu đọc lặp "
          f"hoặc đọc thiếu ({len(nghi)/len(ket_qua)*100:.1f}%)")
    print(f"Chi tiết mọi câu: {OUT.relative_to(ROOT)}\n\nCâu cần nghe lại:")
    for sid, g, text, nghe, diem in nghi:
        print(f"  [{dau_hieu(text, nghe)}] điểm {diem:.2f}  {sid} [{ten.get(g, g)[:22]}]")
        print(f"       sách : {text[:100]}")
        print(f"       nghe : {nghe[:100]}")


if __name__ == "__main__":
    main(sys.argv[1:])
