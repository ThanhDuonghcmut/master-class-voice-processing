"""Cài môi trường bằng BẤT KỲ Python nào có sẵn trên máy (>= 3.8), macOS / Windows / Linux.

    python3 scripts/setup.py          # macOS / Linux
    py -3 scripts/setup.py            # Windows (hoặc: python scripts\\setup.py)

Logic:
  1. Python đang chạy là 3.10–3.13  → dùng luôn: `python -m venv .venv` + pip install.
  2. Không phải (vd 3.9, 3.14)       → cài `uv` (qua pip, hoặc dùng uv đã có), uv tự tải
                                       Python 3.12 rồi tạo .venv và cài thư viện.
  3. Cuối cùng chạy scripts/00_check_env.py trong .venv để xác nhận.

Đổi vị trí venv: python3 scripts/setup.py --venv ten_khac
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Console Windows mặc định không phải UTF-8 → in tiếng Việt vào file/pipe sẽ lỗi
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
REQ = ROOT / "requirements.txt"
SUPPORTED = ((3, 10), (3, 13))
UV_PYTHON = "3.12"
WIN = sys.platform == "win32"


def venv_python(venv):
    return venv / ("Scripts/python.exe" if WIN else "bin/python")


def run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def find_uv():
    """Trả về lệnh chạy uv dạng list, hoặc None."""
    if shutil.which("uv"):
        return ["uv"]
    try:
        subprocess.run([sys.executable, "-m", "uv", "--version"], check=True, capture_output=True)
        return [sys.executable, "-m", "uv"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def install_uv():
    print("→ Cài uv bằng pip của Python hiện tại …")
    try:
        run([sys.executable, "-m", "pip", "install", "--user", "--quiet", "uv"])
    except subprocess.CalledProcessError:
        run([sys.executable, "-m", "pip", "install", "--quiet", "uv"])
    uv = find_uv()
    if not uv:
        sys.exit("Không cài được uv qua pip. Cài tay rồi chạy lại:\n"
                 "  macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh\n"
                 "  Windows:     powershell -ExecutionPolicy ByPass -c \"irm https://astral.sh/uv/install.ps1 | iex\"")
    return uv


def main():
    venv = ROOT / (sys.argv[sys.argv.index("--venv") + 1] if "--venv" in sys.argv else ".venv")
    v = sys.version_info[:2]
    print(f"Python đang chạy: {sys.version.split()[0]} ({sys.executable})")
    if venv.exists():
        print(f"→ {venv.name} đã tồn tại, chỉ cài/cập nhật thư viện")
        py = venv_python(venv)
        uv = find_uv()
        if uv:
            run(uv + ["pip", "install", "--python", py, "-r", REQ])
        else:
            run([py, "-m", "pip", "install", "-r", REQ])
    elif SUPPORTED[0] <= v <= SUPPORTED[1]:
        print(f"→ Python {v[0]}.{v[1]} nằm trong 3.10–3.13, dùng luôn để tạo {venv.name}")
        run([sys.executable, "-m", "venv", venv])
        py = venv_python(venv)
        run([py, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
        run([py, "-m", "pip", "install", "-r", REQ])
    else:
        print(f"→ Python {v[0]}.{v[1]} KHÔNG được VieNeu hỗ trợ (cần 3.10–3.13); dùng uv tải Python {UV_PYTHON}")
        uv = find_uv() or install_uv()
        run(uv + ["venv", "--python", UV_PYTHON, venv])
        py = venv_python(venv)
        run(uv + ["pip", "install", "--python", py, "-r", REQ])

    print("\n→ Kiểm tra môi trường vừa tạo:")
    result = subprocess.run([str(py), str(ROOT / "scripts" / "00_check_env.py")])
    print("\nTiếp theo:", f"{py.relative_to(ROOT)} scripts/00_check_env.py --tts" if WIN
          else "make check-tts && make trial")
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
