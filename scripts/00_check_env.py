"""Bước 0: kiểm tra máy có chạy được pipeline (đặc biệt VieNeu-TTS) không.

In ra từng mục với [OK] / [WARN] / [FAIL]. Thoát mã 1 nếu có FAIL.
Thêm --tts để tải model và đọc thử 1 câu → đo RTF thật, ước lượng thời gian cả sách.

    .venv/bin/python scripts/00_check_env.py
    .venv/bin/python scripts/00_check_env.py --tts
"""
import importlib
import os
import platform
import shutil
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

ROOT = Path(__file__).resolve().parents[1]
HF_CACHE = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
MODEL_REPOS = ["models--pnnbao-ump--VieNeu-TTS-v3-Turbo",
               "models--OpenMOSS-Team--MOSS-Audio-Tokenizer-Nano-ONNX"]
BOOK_AUDIO_HOURS = 9.9          # đo từ book.json: 439k ký tự × 81 s/1000 ký tự
MIN_RAM_GB, MIN_DISK_GB = 8, 10  # model ~2-3 GB RAM; wav trung gian ~3,5 GB + mp3 + zip

fails = 0


def report(level, msg):
    global fails
    fails += level == "FAIL"
    print(f"[{level}] {msg}")


def check_python():
    v = sys.version_info
    ok = (3, 10) <= (v.major, v.minor) <= (3, 13)
    report("OK" if ok else "FAIL",
           f"Python {v.major}.{v.minor}.{v.micro} — VieNeu cần 3.10–3.13"
           + ("" if ok else ". Tạo lại venv: uv venv --python 3.12 .venv"))


def check_packages():
    missing = []
    for mod, pkg in [("vieneu", "vieneu"), ("onnxruntime", "onnxruntime"), ("pymupdf", "pymupdf"),
                     ("soundfile", "soundfile"), ("lameenc", "lameenc"), ("numpy", "numpy")]:
        try:
            importlib.import_module(mod)
        except Exception:
            missing.append(pkg)
    report("OK" if not missing else "FAIL",
           "Thư viện đủ" if not missing else f"Thiếu {missing} → make setup")


def check_hardware():
    machine, cores = platform.machine(), os.cpu_count() or 0
    report("OK", f"CPU {machine}, {cores} nhân — ONNX dùng ~7 luồng; RTF đo trên Apple M5 Pro = 0,12")
    ram = None
    try:
        if sys.platform == "darwin":
            ram = int(os.popen("sysctl -n hw.memsize").read()) / 2**30
        elif sys.platform.startswith("linux"):
            ram = int(next(l for l in open("/proc/meminfo") if l.startswith("MemTotal")).split()[1]) / 2**20
    except Exception:
        pass
    if ram is None:
        report("WARN", "Không đọc được dung lượng RAM; cần ≥ 8 GB")
    else:
        report("OK" if ram >= MIN_RAM_GB else "WARN", f"RAM {ram:.0f} GB (cần ≥ {MIN_RAM_GB} GB)")
    free = shutil.disk_usage(ROOT).free / 2**30
    report("OK" if free >= MIN_DISK_GB else "WARN", f"Ổ đĩa trống {free:.0f} GB (cần ≥ {MIN_DISK_GB} GB cho wav trung gian)")
    if machine in ("x86_64", "AMD64"):
        report("WARN", "CPU x86: pipeline dùng fp32 nên không cần VNNI; RTF có thể ~0,5 (chậm 4× so với M-series)")


def check_model_cache():
    for repo in MODEL_REPOS:
        d = HF_CACHE / repo / "snapshots"
        if not d.exists():
            report("WARN", f"Chưa tải model {repo.split('--')[-1]} — lần chạy đầu sẽ tải từ HuggingFace (cần mạng)")
            continue
        links = [p for p in d.rglob("*") if p.is_symlink()]
        if links:
            report("FAIL", f"Model {repo.split('--')[-1]} tải dạng symlink → onnxruntime từ chối. "
                           f"Xoá {HF_CACHE / repo} rồi chạy lại (script đã đặt HF_HUB_DISABLE_SYMLINKS=1)")
        else:
            report("OK", f"Model {repo.split('--')[-1]} đã có trong cache, không symlink")


def check_inputs():
    pdf = ROOT / "input" / "nhung-tam-long-cao-ca.pdf"
    report("OK" if pdf.exists() else "FAIL", f"{pdf.relative_to(ROOT)} {'có' if pdf.exists() else 'THIẾU'}")


def tts_smoke_test():
    from vieneu import Vieneu
    print("... tải model (lần đầu có thể vài phút)")
    t0 = time.time()
    tts = Vieneu()
    print(f"    tải model {time.time()-t0:.0f} s")
    text = "Hôm nay là ngày khai trường. Mấy tháng nghỉ hè của chúng tôi đã đi qua như một giấc mộng."
    tts.infer("Xin chào.", voice="Đức Trí")   # làm nóng: lần infer đầu chậm gấp 3 do khởi tạo graph
    t0 = time.time()
    audio = tts.infer(text, voice="Đức Trí")
    dt, dur = time.time() - t0, len(audio) / 48000
    rtf = dt / dur
    est = BOOK_AUDIO_HOURS * rtf
    report("OK" if rtf < 1 else "WARN",
           f"TTS chạy được: {dur:.1f} s audio trong {dt:.1f} s → RTF {rtf:.2f}; "
           f"cả sách ({BOOK_AUDIO_HOURS} h audio) ước ~{est*60:.0f} phút máy"
           + ("" if rtf < 1 else " — chậm hơn thời gian thực, cân nhắc máy khác"))


if __name__ == "__main__":
    check_python()
    check_packages()
    check_hardware()
    check_model_cache()
    check_inputs()
    if "--tts" in sys.argv and not fails:
        tts_smoke_test()
    print("\nKết quả:", "có lỗi phải sửa" if fails else "sẵn sàng")
    sys.exit(1 if fails else 0)
