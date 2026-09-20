# Sách nói DAISY 3 — *Những tấm lòng cao cả*

Chuyển PDF có text sang sách nói DAISY 3 (văn bản + audio đồng bộ **từng câu**, mục lục 2 cấp tháng → truyện) bằng TTS tiếng Việt mã nguồn mở [VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS), chạy hoàn toàn offline trên CPU.

Đồ án môn Xử lý tiếng nói. Mọi lệnh bên dưới là Python thuần; macOS/Linux có thể dùng lối tắt tương đương trong `Makefile` (`make help`). Hướng dẫn gốc: `input/[VR] DAISY Guidelines.pdf`. Quyết định kỹ thuật và lý do: [KE-HOACH.md](KE-HOACH.md).

## QA (nghe và ghi nhận lỗi) trong 3 lệnh — không cần cài model, không cần venv

Cần **Git** và **Python 3** (bản nào cũng được): macOS có sẵn (`xcode-select --install`); Windows cài [Git](https://git-scm.com/download/win) và [Python](https://www.python.org/downloads/) (tick *Add to PATH*); Ubuntu `sudo apt install git python3`.

```bash
git clone https://github.com/ThanhDuonghcmut/master-class-voice-processing.git
cd master-class-voice-processing
python3 scripts/qa.py            # kiểm máy → lần đầu tự tải sách từ GitHub Release (~290 MB) → mở http://localhost:8765/qa.html
python3 scripts/qa.py submit     # nghe xong, đã bấm Xuất CSV → commit + push lên repo
```

Windows: thay `python3` bằng `py -3` (hoặc `python`), gõ trong PowerShell hay Git Bash đều được.

`qa.py` tự kiểm git / Python / đĩa / cổng, in `[OK]`/`[FAIL]` kèm cách sửa. Các lệnh khác: `python3 scripts/qa.py check` (chỉ kiểm), `python3 scripts/qa.py fetch --force` (tải lại khi có release mới).

**Chia 3 phần cân thời lượng** (hiện sẵn trong mục lục trái của trang QA):

| Phần | Thời lượng | Từ | Đến |
|---|---|---|---|
| 1 | 3h18 | MỞ ĐẦU | Franti bị đuổi học (THÁNG GIÊNG) |
| 2 | 3h36 | Cậu bé đánh trống người Sardegna | Thầy giáo của bố (THÁNG TƯ) |
| 3 | 3h20 | Dưỡng bệnh | Từ biệt |

**Trong trang QA:**

| Thao tác | Kết quả |
|---|---|
| Điền **tên** ở ô trên cùng | vào tên file CSV, không đè nhau |
| Bấm truyện ở mục lục trái | hiện toàn bộ câu, mỗi dòng `id · mốc giây · câu` |
| Bấm vào câu / `↓` `↑` | phát đúng câu đó |
| **▶ Nghe cả truyện**, `Space` | nghe liền, câu đang đọc bôi sáng |
| Tick ☐ cạnh câu, gõ ghi chú | ghi nhận lỗi (lưu trong trình duyệt, đóng tab không mất) |
| **⬇ Xuất CSV lỗi** | ghi `qa/qa_<tên>_<ngày>_<giờ-phút-giây>.csv` thẳng vào repo |

Ghi chú nói **lỗi gì, ở từ nào**: "nghỉ sai sau *giáo*", "đọc *4,444* thành bốn nghìn", "tên *Garrone* đọc lạ". Xuất nhiều lần cũng được — mỗi lần một file, người gộp sẽ hợp nhất.

Có bản sách mới (release mới): `python3 scripts/qa.py fetch --force`.

## Người giữ repo: gộp QA và sửa cách đọc

Cần `.venv` (mục *Cài đặt* bên dưới). Đặt `PY=.venv/bin/python` (Windows: `$PY = ".venv\Scripts\python.exe"` và gọi `& $PY …`).

```bash
git pull
$PY scripts/gop_qa.py qa/*.csv      # gộp CSV vào sua_cach_doc.csv (mỗi id một dòng, giữ ghi chú mọi người)
# mở sua_cach_doc.csv, điền cột speech = bản đọc mới cho từng id
$PY scripts/01_extract_pdf.py       # áp bản đọc mới vào book.json
$PY scripts/02_tts.py               # chỉ đọc lại câu có bản đọc đổi (vài giây/câu)
$PY scripts/03_concat_mp3.py        # ghép lại các truyện có câu đổi
$PY scripts/04_build_daisy.py       # dựng lại sách + out/qa.html
python3 scripts/qa.py               # nghe lại đúng các câu đó
```

Đưa bản mới lên GitHub Release (cần [gh](https://cli.github.com) đã `gh auth login`):

```bash
cd out/Nhung_tam_long_cao_ca && zip -0 ../Nhung_tam_long_cao_ca.zip * && cd ../..
gh release create v0.2-qa out/Nhung_tam_long_cao_ca.zip out/qa.html --title v0.2-qa --notes "Sách DAISY + trang QA"
```

`sua_cach_doc.csv` chỉ đổi **bản đọc**; chữ hiển thị trong sách vẫn là nguyên văn. Cột `speech` trống = đã ghi nhận, chưa sửa. Cách chữa hay dùng: thêm dấu phẩy để ép ngắt nhịp ("Thầy giáo mới, ngay từ sáng…"), viết số thành chữ ("4 phẩy 444"), phiên âm tên riêng.

> **Không đổi quy tắc tách câu sau khi đã QA.** Id đánh tuần tự từ đầu sách; đổi cách tách câu là id trôi và CSV lệch. Bước 1 sẽ dừng nếu có id trong CSV không còn tồn tại.

## Người dựng sách: cài đặt

Chỉ cần khi muốn chạy TTS / dựng lại sách. QA thì không cần mục này.

Cần ≥ 8 GB RAM, ≥ 10 GB đĩa trống, mạng cho lần tải model đầu (~1 GB). VieNeu-TTS chỉ chạy trên **Python 3.10–3.13**; `scripts/setup.py` tự xử lý việc này:

| Máy đang có | `setup.py` làm gì |
|---|---|
| Python 3.10–3.13 | dùng luôn: tạo `.venv` bằng `python -m venv`, cài `requirements.txt` bằng pip |
| Python khác (3.9, 3.14…) | cài [uv](https://docs.astral.sh/uv/) qua pip, uv **tự tải Python 3.12** và tạo `.venv` |
| Đã có uv | dùng uv luôn, không cần Python đúng bản |

Cuối cùng `setup.py` chạy `00_check_env.py` và in bảng `[OK]/[WARN]/[FAIL]`.

```bash
python3 scripts/setup.py                  # tạo .venv + cài thư viện; Python không phải 3.10–3.13 thì tự cài uv và tải 3.12
PY=.venv/bin/python                       # Windows: $PY = ".venv\Scripts\python.exe" rồi gọi & $PY …
$PY scripts/00_check_env.py --tts         # kiểm máy, tải model (~1 GB, một lần), đọc thử 1 câu → RTF + ước lượng thời gian
$PY scripts/01_extract_pdf.py             # bước 1: PDF → build/book.json
$PY scripts/02_tts.py front lv1-02 lv2-001 lv2-002   # bước 2 dựng thử vài nhóm (~3 phút); bỏ tham số = cả sách (~70 phút M5 Pro)
$PY scripts/03_concat_mp3.py              # bước 3: ghép mp3 + timing.json
$PY scripts/04_build_daisy.py             # bước 4: out/Nhung_tam_long_cao_ca/ + out/qa.html
python3 scripts/qa.py                     # nghe bản vừa dựng trong trang QA
```

Mở bằng Thorium Reader (`brew install --cask thorium`): nén thư mục sách thành zip (`cd out && zip -0 -r sach.zip Nhung_tam_long_cao_ca`) rồi Import **file zip** — import thẳng `package.opf` Thorium không thấy audio, đọc bằng TTS hệ thống.

### Chạy dở dang

Cứ chạy lại lệnh cũ — bước TTS bỏ qua câu đã có wav, bước 3 bỏ qua nhóm đã có mp3 mới hơn wav. Muốn đọc lại một truyện: xoá `build/wav/<nhóm>/` rồi chạy lại.

## Nộp bài

1. Điền `metadata.json`: mọi giá trị `CHUA_DIEN_*` (ISBN, sourceURL, người đóng góp, MSHV).
2. `$PY scripts/04_build_daisy.py --strict && $PY scripts/05_package.py` → `out/<MSHV1_MSHV2>/Nhung_tam_long_cao_ca/{Nhung_tam_long_cao_ca.zip, *_sha256sums.txt}` đúng cây thư mục slide 21.

## Pipeline

```mermaid
flowchart LR
    A[input/*.pdf] -->|01_extract_pdf| B[build/book.json]
    B -->|02_tts| C[build/wav/nhóm/câu.wav]
    C -->|03_concat_mp3| D[build/mp3 + timing.json]
    B --> E
    D -->|04_build_daisy| E[out/slug/ dtbook·smil·ncx·opf]
    E -->|05_package| F[out/MSHV/slug.zip + sha256]
```

| Bước | Script | Ra | Chạy lại khi |
|---|---|---|---|
| 0 | `00_check_env.py [--tts]` | báo cáo OK/WARN/FAIL | máy mới |
| 1 | `01_extract_pdf.py` | `build/book.json` — 99 heading, ~5.000 câu, 92 chú thích, đối chiếu tự động với bookmark PDF | sửa quy tắc tách câu / `SOURCE_FIXES` |
| 2 | `02_tts.py [nhóm…]` | `build/wav/<nhóm>/<id>.wav`, 1 file / câu | đổi giọng (`VOICE` trong `02_tts.py`), xoá wav muốn đọc lại |
| 3 | `03_concat_mp3.py` | `build/mp3/<nhóm>.mp3` + `timing.json` (clipBegin/End tính từ số mẫu PCM) | đổi khoảng nghỉ (`PAUSE_AFTER` trong `book_units.py`) |
| 4 | `04_build_daisy.py [--strict]` | `out/<slug>/` (chỉ gồm nhóm đã có audio, nên dựng thử vẫn mở được) + `out/qa.html` | luôn rẻ (giây) |
| 5 | `05_package.py` | zip + sha256 | trước khi nộp |
| QA | `qa.py [check\|fetch\|submit]` · `gop_qa.py` | trang nghe-ghi nhận, nộp CSV; gộp CSV | mỗi vòng QA |

**Nhóm** = 1 file mp3 = 1 file smil: `front` (tên sách, tác giả) · `lv1-NN` (tiêu đề tháng, riêng `lv1-01` MỞ ĐẦU có nội dung) · `lv2-NNN` (88 truyện). 92 chú thích đọc **ngay sau đoạn** chứa `[n]`, mở đầu bằng "Chú thích:", đánh dấu skippable (Thorium: tắt/bật trong cài đặt đọc). Xem id trong `build/book.json`.

## Thư mục

| | Chứa | Không chứa |
|---|---|---|
| `input/` | PDF nguồn, slide hướng dẫn | — |
| `scripts/` | 6 bước đánh số + `book_units.py` (thứ tự đọc dùng chung) + `qa_template.html`, `dtbook.css`, `resources.res` | dữ liệu |
| `build/` | trung gian, **xoá được**, không commit | sản phẩm nộp |
| `out/` | sách DAISY và zip nộp, không commit | — |
| `metadata.json` | 9 trường slide 17 + MSHV | — |
| `sua_cach_doc.csv` | bản đọc sửa theo id câu (kết quả QA) | chữ hiển thị |
| `qa/` | CSV người nghe xuất từ trang QA, đầu vào của `gop_qa.py` | — |
| `scripts/qa.py` | tải sách từ Release, server trang QA, nộp CSV — **stdlib thuần**, không cần venv | — |

Thêm bước mới → file `scripts/0N_ten.py` (+ target trong `Makefile` nếu muốn); thêm loại đơn vị đọc → sửa `book_units.py` (2–4 tự khớp).

## Cạm bẫy đã gặp

- **onnxruntime ≥ 1.30 từ chối model qua symlink** của HuggingFace cache. Script đã đặt `HF_HUB_DISABLE_SYMLINKS=1`; nếu từng tải model trước khi dùng repo này, `00_check_env.py` báo FAIL kèm lệnh xoá cache.
- **Python 3.14** không cài được VieNeu (chỉ 3.10–3.13) → `setup.py` kiểm phiên bản, lệch thì dùng uv tải 3.12.
- Lần `infer` đầu tiên chậm gấp 3 (khởi tạo graph) — `00_check_env.py --tts` đã làm nóng trước khi đo.
- PDF do calibre sinh mất chữ **Â hoa** ("châu u") → `SOURCE_FIXES` trong `01_extract_pdf.py`.
- pymupdf tách block khi có chú thích `[n]` đổi chiều cao dòng → quy tắc nối đoạn theo dấu câu + chữ thường.
- **Trình đọc DAISY bỏ qua im lặng nằm giữa hai clip** → clip của câu phải bao luôn khoảng nghỉ sau nó (`clipEnd` = `clipBegin` câu kế).
- **Thorium đổi mọi thẻ DTBook thành `<div>`** (kể cả `noteref`) → `[n]` xuống dòng; chữa bằng `dtbook.css` đi kèm sách (Thorium viết lại selector thành `.noteref_R2`).
- Thorium nhận DAISY qua **zip/thư mục**, không phải `package.opf` lẻ (mở .opf nó dùng TTS hệ thống → giọng khác).
- VieNeu ngắt nhịp sai ở câu nhập nhằng cú pháp và đọc "4,444" thành bốn nghìn → không tự phát hiện được, chỉ bắt bằng tai qua QA rồi sửa bản đọc.

## Kiểm chứng đã cài trong script

- Bước 1 fail nếu heading trích ≠ 99 bookmark PDF hoặc noteref ↔ chú thích không khớp 1-1.
- Bước 4 fail nếu số `smilref` trong dtbook ≠ số `<par>` trong smil hoặc có smilref trỏ tới id không tồn tại; `dtb:totalTime` tính từ mp3 thật.
- Bước 5 fail nếu thiếu nhóm audio hoặc còn `CHUA_DIEN`.
- `xmllint --noout out/Nhung_tam_long_cao_ca/*.{xml,smil,ncx,opf,res}`: well-formed cho mọi file XML.
