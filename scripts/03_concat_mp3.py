"""Bước 3: build/wav/<nhóm>/*.wav → build/mp3/<nhóm>.mp3 + build/timing.json.

Mỗi nhóm (truyện / tháng-không-truyện / chú thích) ghép thành MỘT mp3 theo đúng thứ tự đọc,
cắt im lặng đầu-cuối từng clip về mức đều nhau rồi chèn khoảng nghỉ theo loại đơn vị
(book_units.PAUSE_AFTER). Vị trí clipBegin/clipEnd tính từ số mẫu PCM → chính xác tuyệt đối.

timing.json: {nhóm: {"mp3": "...", "duration": giây, "clips": [[id, begin, end], ...]}}
Nhóm nào thiếu wav thì bỏ qua (dựng thử vài truyện vẫn chạy được). Nhóm đã có mp3 mới hơn
mọi wav của nó thì không ghép lại.

    .venv/bin/python scripts/03_concat_mp3.py
"""
import json
import sys

# Console Windows mặc định không phải UTF-8 → in tiếng Việt vào file/pipe sẽ lỗi
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import lameenc
import numpy as np
import soundfile as sf

from book_units import BUILD, PAUSE_AFTER, groups_in_order, iter_units, load_book

WAV_DIR, MP3_DIR = BUILD / "wav", BUILD / "mp3"
TIMING = BUILD / "timing.json"
SR = 48_000
BITRATE_KBPS = 64          # mono 48 kHz: sách nói DAISY thường 32–64 kbps; 9,9 h ≈ 285 MB
SILENCE_THRESHOLD = 0.01   # biên độ coi là im lặng (float32, đỉnh = 1.0)
KEEP_MARGIN_S = 0.05       # giữ lại 50 ms im lặng thật ở hai đầu clip sau khi cắt


def trim(audio):
    idx = np.where(np.abs(audio) > SILENCE_THRESHOLD)[0]
    if len(idx) == 0:
        return audio
    m = int(KEEP_MARGIN_S * SR)
    return audio[max(0, idx[0] - m): min(len(audio), idx[-1] + m)]


def encode_mp3(pcm_float, path):
    enc = lameenc.Encoder()
    enc.set_bit_rate(BITRATE_KBPS)
    enc.set_in_sample_rate(SR)
    enc.set_channels(1)
    enc.set_quality(2)                      # 2 = chất lượng cao, chậm hơn chút
    pcm16 = (np.clip(pcm_float, -1, 1) * 32767).astype(np.int16)
    path.write_bytes(enc.encode(pcm16.tobytes()) + enc.flush())


def build_group(group, units):
    wavs = [WAV_DIR / group / f"{u.id}.wav" for u in units]
    missing = [w.name for w in wavs if not w.exists()]
    if missing:
        return None, f"thiếu {len(missing)} wav (vd {missing[0]})"
    out = MP3_DIR / f"{group}.mp3"
    if out.exists() and out.stat().st_mtime > max(w.stat().st_mtime for w in wavs) and TIMING.exists():
        old = json.loads(TIMING.read_text(encoding="utf-8")).get(group)
        if old and old.get("pauses") == PAUSE_AFTER:      # đổi khoảng nghỉ → phải ghép lại
            return old, "giữ nguyên"
    parts, clips, pos = [], [], 0
    for u, w in zip(units, wavs):
        audio, sr = sf.read(w, dtype="float32")
        assert sr == SR, f"{w}: {sr} Hz, cần {SR}"
        audio = trim(audio)
        clips.append([u.id, round(pos / SR, 3), round((pos + len(audio)) / SR, 3)])
        pause = PAUSE_AFTER["para_end" if u.para_end and u.kind == "sent" else
                            "note_end" if u.para_end and u.kind == "note_sent" else u.kind]
        gap = np.zeros(int(pause * SR), dtype=np.float32)
        parts += [audio, gap]
        pos += len(audio) + len(gap)
    pcm = np.concatenate(parts)
    MP3_DIR.mkdir(parents=True, exist_ok=True)
    encode_mp3(pcm, out)
    return {"mp3": out.name, "duration": round(len(pcm) / SR, 3), "pauses": PAUSE_AFTER,
            "clips": clips}, "ghép mới"


def main():
    book = load_book()
    by_group = {}
    for u in iter_units(book):
        by_group.setdefault(u.group, []).append(u)
    timing = json.loads(TIMING.read_text(encoding="utf-8")) if TIMING.exists() else {}
    total = 0.0
    for group in groups_in_order(book):
        result, status = build_group(group, by_group[group])
        if result:
            timing[group] = result
            total += result["duration"]
            print(f"  {group:8s} {len(result['clips']):4d} clip {result['duration']/60:6.1f} phút  {status}")
        else:
            print(f"  {group:8s} bỏ qua: {status}")
    TIMING.write_text(json.dumps(timing, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Tổng {len(timing)}/{len(by_group)} nhóm, {total/3600:.2f} giờ audio → {TIMING.relative_to(BUILD.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
