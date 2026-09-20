"""Gộp các file qa_*.csv đồng đội xuất từ trang QA vào sua_cach_doc.csv.

Mỗi id chỉ một dòng: id đã có thì nối thêm ghi chú (không ghi đè cột speech đã sửa).
Cột speech để trống = mới ghi nhận, chưa sửa cách đọc; người sửa điền tay rồi `make all`.

    .venv/bin/python scripts/gop_qa.py qa/*.csv
"""
import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
FIXES = ROOT / "sua_cach_doc.csv"
FIELDS = ["id", "speech", "ghi_chu"]


def main(paths):
    rows = {}
    if FIXES.exists():
        with FIXES.open(encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                rows[r["id"]] = {k: r.get(k, "") for k in FIELDS}
    before = len(rows)
    for path in paths:
        with Path(path).open(encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                sid, note = r["id"].strip(), r.get("ghi_chu", "").strip()
                tag = f"[{Path(path).stem}] {note}" if note else f"[{Path(path).stem}]"
                if sid in rows:
                    if tag not in rows[sid]["ghi_chu"]:
                        rows[sid]["ghi_chu"] = (rows[sid]["ghi_chu"] + " | " + tag).strip(" |")
                else:
                    rows[sid] = {"id": sid, "speech": "", "ghi_chu": f"{tag} — câu gốc: {r.get('cau', '')}"}
    with FIXES.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for sid in sorted(rows):
            w.writerow(rows[sid])
    pending = sum(1 for r in rows.values() if not r["speech"])
    print(f"{FIXES.name}: {before} → {len(rows)} dòng; {pending} câu chưa điền cột speech")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
