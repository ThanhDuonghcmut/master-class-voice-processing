"""QA sách nói — mọi thứ đồng đội cần, CHỈ dùng thư viện chuẩn (không cần .venv, không cần model).

    python3 scripts/qa.py            # thiếu sách → tải từ GitHub Release; rồi mở trang QA http://localhost:8765/qa.html
    python3 scripts/qa.py submit     # commit + push mọi CSV mới trong qa/
    python3 scripts/qa.py fetch      # chỉ tải/cập nhật sách từ release mới nhất (--force để tải lại)

Windows: thay `python3` bằng `py -3` (hoặc `python`).

Trang mở bằng file:// không được trình duyệt cho ghi file, nên trang chạy qua server này; nút Xuất
POST về /save → qa/qa_<ten>_<YYYY-MM-DD_HHMMSS>.csv trong repo.
"""
import json
import re
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

ROOT = Path(__file__).resolve().parents[1]
OUT, QA = ROOT / "out", ROOT / "qa"
SLUG = json.loads((ROOT / "metadata.json").read_text(encoding="utf-8"))["slug"]
BOOK_DIR, QA_HTML = OUT / SLUG, OUT / "qa.html"
PORT = 8765


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


def fetch(force=False):
    if BOOK_DIR.joinpath("package.opf").exists() and QA_HTML.exists() and not force:
        return
    base = f"https://github.com/{repo_slug()}/releases/latest/download/"
    OUT.mkdir(exist_ok=True)
    print("Tải sách từ release mới nhất (~290 MB, một lần)…")
    zpath = OUT / f"{SLUG}.zip"
    download(base + f"{SLUG}.zip", zpath)
    download(base + "qa.html", QA_HTML)
    BOOK_DIR.mkdir(exist_ok=True)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(BOOK_DIR)
    zpath.unlink()
    print(f"→ {BOOK_DIR.relative_to(ROOT)}/ ({sum(1 for _ in BOOK_DIR.iterdir())} file)")


# ---------- server trang QA ----------
class Handler(SimpleHTTPRequestHandler):
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
    print(f"Trang QA: {url}\nCtrl+C để dừng. CSV xuất từ trang sẽ ghi vào qa/; xong thì: python3 scripts/qa.py submit")
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
    print(f"Đã push {len(new)} file. Người giữ repo: make merge-qa → điền speech → make fix")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "submit":
        submit()
    elif cmd == "fetch":
        fetch(force="--force" in sys.argv)
    else:
        fetch()
        serve()
