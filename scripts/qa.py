"""QA sách nói — mọi thứ người nghe cần, CHỈ dùng thư viện chuẩn (không cần .venv, không cần model).

    make qa            → qa.py          : kiểm máy, thiếu sách → tải từ GitHub Release, mở http://localhost:8765/qa.html
    make submit-qa     → qa.py submit   : commit + push mọi CSV mới trong qa/
    make fetch         → qa.py fetch --force : tải lại sách khi có release mới
    make qa-check      → qa.py check    : chỉ kiểm máy

Trang mở bằng file:// không được trình duyệt cho ghi file, nên trang chạy qua server này; nút Xuất
POST về /save → qa/qa_<ten>_<YYYY-MM-DD_HHMMSS>.csv trong repo.
"""
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import webbrowser
import zipfile
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os

ROOT = Path(__file__).resolve().parents[1]
OUT, QA = ROOT / "out", ROOT / "qa"
SLUG = json.loads((ROOT / "metadata.json").read_text(encoding="utf-8"))["slug"]
BOOK_DIR, QA_HTML = OUT / SLUG, OUT / "qa.html"
DAU_BAN = OUT / ".phien_ban"        # ghi tên bản đã tải, để biết khi nào cần tải lại
PORT = 8765


# ---------- tiền kiểm ----------
def check():
    """Mọi thứ QA cần; in [OK]/[FAIL], thoát 1 nếu FAIL."""
    import shutil
    import socket
    fails = 0

    def report(ok, msg, fix=""):
        nonlocal fails
        fails += not ok
        print(f"[{'OK' if ok else 'FAIL'}] {msg}" + ("" if ok else f" → {fix}"))

    v = sys.version_info
    report(v >= (3, 8), f"Python {v.major}.{v.minor} (QA chỉ cần ≥ 3.8, bản nào cũng được)", "cài Python từ python.org")
    report(shutil.which("git") is not None, "git có sẵn", "cài Git (git-scm.com)")
    try:
        remote = repo_slug()
        report(True, f"repo GitHub: {remote}")
    except (subprocess.CalledProcessError, SystemExit):
        report(False, "remote origin trỏ GitHub", "chạy trong thư mục đã git clone")
    free = shutil.disk_usage(ROOT).free / 2**30
    report(free >= 1, f"đĩa trống {free:.0f} GB (sách ~0,3 GB)", "dọn đĩa")
    have_book = BOOK_DIR.joinpath("package.opf").exists() and QA_HTML.exists()
    print(f"[{'OK' if have_book else '..'}] sách trong out/: {'đã có' if have_book else 'chưa có, sẽ tải từ release'}")
    with socket.socket() as sock:
        busy = sock.connect_ex(("127.0.0.1", PORT)) == 0
    report(not busy, f"cổng {PORT} trống", "trang QA đang chạy ở terminal khác? dùng tab đã mở hoặc Ctrl+C bên đó")
    if fails:
        sys.exit("Có lỗi phải sửa trước.")


# ---------- tải sách từ GitHub Release ----------
def repo_slug():
    url = subprocess.run(["git", "-C", str(ROOT), "remote", "get-url", "origin"],
                         capture_output=True, text=True, check=True).stdout.strip()
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    if not m:
        sys.exit(f"Không nhận ra repo GitHub từ remote: {url}")
    return m.group(1)


def download(url, dest):
    shown = [-1]

    def hook(n, size, total):
        mb = n * size // 2**20
        if total > 0 and mb != shown[0]:            # in mỗi MB, không in mỗi block 8 KB
            shown[0] = mb
            print(f"\r  {dest.name}: {mb:4d}/{total/2**20:.0f} MB", end="", flush=True)
    urllib.request.urlretrieve(url, dest, hook)
    print()


def ban_moi_nhat():
    """Tên bản phát hành mới nhất trên GitHub, hoặc None nếu không hỏi được (máy không có mạng)."""
    try:
        with urllib.request.urlopen(
                f"https://api.github.com/repos/{repo_slug()}/releases/latest", timeout=10) as r:
            return json.load(r).get("tag_name")
    except Exception:
        return None


def fetch(force=False):
    da_co = BOOK_DIR.joinpath("package.opf").exists() and QA_HTML.exists()
    ban_dang_co = DAU_BAN.read_text(encoding="utf-8").strip() if DAU_BAN.exists() else None
    ban_moi = ban_moi_nhat()
    if da_co and not force:
        if ban_moi is None:
            print(f"Không hỏi được bản mới (mất mạng?), dùng sách đang có"
                  f"{' — bản ' + ban_dang_co if ban_dang_co else ''}.")
            return
        if ban_dang_co == ban_moi:
            print(f"Sách đang có đã là bản mới nhất ({ban_moi}).")
            return
        print(f"Có bản mới: {ban_dang_co or 'bản cũ'} → {ban_moi}. Xoá sách cũ rồi tải lại.")
        shutil.rmtree(BOOK_DIR, ignore_errors=True)
        QA_HTML.unlink(missing_ok=True)
    base = f"https://github.com/{repo_slug()}/releases/latest/download/"
    OUT.mkdir(exist_ok=True)
    print(f"Tải sách bản {ban_moi or 'mới nhất'} (~290 MB, một lần)…")
    zpath = OUT / f"{SLUG}.zip"
    download(base + f"{SLUG}.zip", zpath)
    download(base + "qa.html", QA_HTML)
    BOOK_DIR.mkdir(exist_ok=True)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(BOOK_DIR)
    zpath.unlink()
    if ban_moi:
        DAU_BAN.write_text(ban_moi, encoding="utf-8")
    print(f"→ {BOOK_DIR.relative_to(ROOT)}/ ({sum(1 for _ in BOOK_DIR.iterdir())} file)"
          + (f", bản {ban_moi}" if ban_moi else ""))


# ---------- server trang QA ----------
class _DoanFile:
    """Bọc file để chỉ trả đúng số byte của đoạn được yêu cầu."""

    def __init__(self, f, con):
        self.f, self.con = f, con

    def read(self, n=-1):
        if self.con <= 0:
            return b""
        d = self.f.read(self.con if n < 0 else min(n, self.con))
        self.con -= len(d)
        return d

    def close(self):
        self.f.close()


class Handler(SimpleHTTPRequestHandler):
    def send_head(self):
        """Hỗ trợ HTTP Range. Thiếu nó thì trình duyệt không nhảy được vào giữa file mp3 dài:
        bấm một câu ở giữa truyện, audio.currentTime bị bỏ qua và phát lại từ đầu truyện."""
        rng = self.headers.get("Range")
        if not rng or not rng.startswith("bytes="):
            return super().send_head()
        path = self.translate_path(self.path)
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404)
            return None
        co = os.fstat(f.fileno()).st_size
        dau, _, cuoi = rng[6:].partition("-")
        dau = int(dau) if dau else 0
        cuoi = int(cuoi) if cuoi else co - 1
        cuoi = min(cuoi, co - 1)
        if dau >= co:
            f.close()
            self.send_error(416)
            return None
        f.seek(dau)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {dau}-{cuoi}/{co}")
        self.send_header("Content-Length", str(cuoi - dau + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        return _DoanFile(f, cuoi - dau + 1)

    def end_headers(self):
        if "Accept-Ranges" not in self._headers_buffer_text():
            self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def _headers_buffer_text(self):
        return b"".join(getattr(self, "_headers_buffer", [])).decode("latin-1", "replace")

    def do_POST(self):
        if self.path != "/save":
            self.send_error(404)
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        who = re.sub(r"[^A-Za-z0-9-]+", "-", body.get("who") or "khong-ten").strip("-") or "khong-ten"
        QA.mkdir(exist_ok=True)
        path = QA / f"qa_{who}_{datetime.now():%Y-%m-%d_%H%M%S}.csv"
        path.write_text(body["csv"], encoding="utf-8")
        n = body["csv"].count("\n") - 1
        print(f"  ghi {path.relative_to(ROOT)} ({n} câu)")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"path": str(path.relative_to(ROOT)), "n": n}).encode())

    def log_message(self, *_):      # tắt log GET từng mp3
        pass


def serve():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), partial(Handler, directory=str(OUT)))
    url = f"http://localhost:{PORT}/qa.html"
    print(f"Trang QA: {url}\nCtrl+C để dừng. CSV xuất từ trang sẽ ghi vào qa/; xong thì: make submit-qa")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng.")


# ---------- nộp CSV ----------
def submit():
    git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], check=True)
    subprocess.run(["git", "-C", str(ROOT), "add", "qa"], check=True)
    new = subprocess.run(["git", "-C", str(ROOT), "diff", "--cached", "--name-only", "--", "qa/*.csv"],
                         capture_output=True, text=True).stdout.split()
    if not new:
        print("qa/ không có CSV mới.")
        return
    names = ", ".join(Path(p).stem for p in new)
    git("commit", "-m", f"qa: ghi nhận lỗi {names}")
    git("pull", "--rebase", "-q")
    git("push")
    print(f"Đã push {len(new)} file. Cảm ơn! (Người giữ repo: make merge-qa → điền speech → make fix)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "submit":
        submit()
    elif cmd == "fetch":
        fetch(force="--force" in sys.argv)
    elif cmd == "check":
        check()
    else:
        check()
        fetch()
        serve()
