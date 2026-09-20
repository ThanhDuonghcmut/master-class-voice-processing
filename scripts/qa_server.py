"""Server cục bộ cho trang QA: phục vụ out/ qua http và nhận CSV ghi thẳng vào qa/.

Vì sao cần: trang mở bằng file:// không được trình duyệt cho ghi file (sandbox), chỉ "tải xuống".
Qua http://localhost thì nút Xuất POST về đây, file rơi đúng qa/<ten>_<YYYY-MM-DD_HHMMSS>.csv trong repo.

    .venv/bin/python scripts/qa_server.py          # mở http://localhost:8765/qa.html, Ctrl+C để dừng
"""
import json
import re
import sys
import webbrowser
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
OUT, QA = ROOT / "out", ROOT / "qa"
PORT = 8765


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


if __name__ == "__main__":
    if not (OUT / "qa.html").exists():
        sys.exit("Chưa có out/qa.html — chạy `make daisy` trước")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), partial(Handler, directory=str(OUT)))
    url = f"http://localhost:{PORT}/qa.html"
    print(f"Trang QA: {url}   (Ctrl+C để dừng; CSV xuất sẽ ghi vào qa/)")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng.")
