"""Bước 5: out/<slug>/ → out/<MSHV1_MSHV2>/<slug>/<slug>.zip + <slug>_sha256sums.txt (cây thư mục slide 21).

Chỉ chạy được khi sách đủ 101 nhóm và metadata không còn CHUA_DIEN (bước 4 --strict).
sha256sums.txt theo định dạng `shasum`, kiểm lại bằng:  shasum -a 256 -c <slug>_sha256sums.txt

    .venv/bin/python scripts/05_package.py
"""
import hashlib
import json
import sys
import zipfile

# Console Windows mặc định không phải UTF-8 → in tiếng Việt vào file/pipe sẽ lỗi
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from book_units import BUILD, ROOT, groups_in_order, load_book, load_metadata


def main():
    meta = load_metadata()
    src = ROOT / "out" / meta["slug"]
    timing = json.loads((BUILD / "timing.json").read_text(encoding="utf-8"))
    expected = groups_in_order(load_book())
    missing = [g for g in expected if g not in timing]
    if missing:
        sys.exit(f"DỪNG: sách chưa đủ audio, thiếu {len(missing)}/{len(expected)} nhóm (vd {missing[:3]})")
    if any(v.startswith("CHUA_DIEN") for v in meta["mshv"]):
        sys.exit("DỪNG: metadata.json chưa điền mshv")
    dest = ROOT / "out" / "_".join(meta["mshv"]) / meta["slug"]
    dest.mkdir(parents=True, exist_ok=True)
    zpath = dest / f'{meta["slug"]}.zip'
    files = sorted(p for p in src.iterdir() if p.is_file())
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.name)
    digest = hashlib.sha256(zpath.read_bytes()).hexdigest()
    sums = dest / f'{meta["slug"]}_sha256sums.txt'
    sums.write_text(f"{digest}  {zpath.name}\n", encoding="utf-8")
    print(f"{zpath.relative_to(ROOT)}  {zpath.stat().st_size/2**20:.0f} MB, {len(files)} file")
    print(f"{sums.relative_to(ROOT)}  sha256={digest[:16]}…")
    print(f"Kiểm: cd {dest.relative_to(ROOT)} && shasum -a 256 -c {sums.name}")


if __name__ == "__main__":
    main()
