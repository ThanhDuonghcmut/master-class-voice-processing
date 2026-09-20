# Sách nói DAISY 3 — Những tấm lòng cao cả.  `make help` để xem lệnh.
# Mọi target chạy trong .venv của repo (tạo bằng `make setup`). Windows không có make: xem README, chạy thẳng scripts/*.py.

PY      ?= .venv/bin/python
PY3     := $(shell command -v python3 || command -v python || echo py -3)   # Python hệ thống cho QA/setup (Windows Git Bash: python hoặc py -3)
GROUPS  ?= front lv1-02 lv2-001 lv2-002 lv2-004   # nhóm dùng cho `make trial`; xem id trong build/book.json
QA_CSV  ?= qa/*.csv                              # file đồng đội xuất từ trang QA
OPEN    := $(shell command -v open || command -v xdg-open)
SHELL   := /bin/bash

.DEFAULT_GOAL := help

help: ## Liệt kê lệnh
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ---------- QA: nghe, ghi nhận, sửa cách đọc ----------

qa: ## QA (không cần .venv): kiểm máy → thiếu sách thì tải từ GitHub Release → mở trang nghe; Xuất CSV ghi vào qa/
	$(PY3) scripts/qa.py

submit-qa: ## Nghe xong: commit + push mọi CSV mới trong qa/
	$(PY3) scripts/qa.py submit

qa-check: ## Chỉ kiểm máy cho QA (git, Python, đĩa, cổng)
	$(PY3) scripts/qa.py check

fetch: ## Tải lại sách + qa.html từ release mới nhất (khi có bản mới)
	$(PY3) scripts/qa.py fetch --force

merge-qa: ## Gộp CSV đồng đội (QA_CSV=qa/*.csv) vào sua_cach_doc.csv, rồi điền tay cột speech
	$(PY) scripts/gop_qa.py $(QA_CSV)

fix: extract tts mp3 daisy ## Áp sua_cach_doc.csv: chỉ đọc lại câu có bản đọc đổi, ghép lại, dựng lại sách
	@echo "→ make qa để nghe lại các câu vừa sửa"

# ---------- Dựng sách ----------

setup: ## Tạo .venv + cài thư viện bằng Python có sẵn; Python không phải 3.10–3.13 thì tự cài uv và tải 3.12
	$(PY3) scripts/setup.py

check: ## Kiểm tra máy: Python, thư viện, RAM, đĩa, cache model
	$(PY) scripts/00_check_env.py

check-tts: ## Như check + tải model và đọc thử 1 câu để đo tốc độ
	$(PY) scripts/00_check_env.py --tts

extract: ## Bước 1: PDF → build/book.json (áp sua_cach_doc.csv)
	$(PY) scripts/01_extract_pdf.py

tts: ## Bước 2: đọc CẢ SÁCH (~70 phút trên M5 Pro); chỉ đọc câu chưa có wav hoặc bản đọc đã đổi
	$(PY) scripts/02_tts.py

tts-groups: ## Bước 2 cho vài nhóm: make tts-groups GROUPS="lv2-001 lv2-002"
	$(PY) scripts/02_tts.py $(GROUPS)

mp3: ## Bước 3: ghép wav → mp3 + timing.json (nhóm nào đủ wav mới ghép)
	$(PY) scripts/03_concat_mp3.py

daisy: ## Bước 4: sinh dtbook/smil/ncx/opf/css → out/<slug>/ + out/qa.html
	$(PY) scripts/04_build_daisy.py

release: ## Đưa sách lên GitHub Release cho đồng đội QA: make release TAG=v0.2-qa
	@test -n "$(TAG)" || { echo "Thiếu TAG=vX.Y-qa"; exit 1; }
	@slug=$$($(PY) -c 'import json;print(json.load(open("metadata.json"))["slug"])'); \
	  rm -f out/$$slug.zip && (cd out/$$slug && zip -q -0 ../$$slug.zip *) && \
	  gh release create $(TAG) out/$$slug.zip out/qa.html --title "$(TAG)" --notes "Sách DAISY + trang QA. Đồng đội: make qa (tự tải)." && rm out/$$slug.zip

package: ## Bước 5: bản nộp — kiểm metadata đủ, zip + sha256 vào out/<MSHV>/
	$(PY) scripts/04_build_daisy.py --strict
	$(PY) scripts/05_package.py

trial: extract tts-groups mp3 daisy ## Dựng thử nhanh (~3 phút) vài truyện, rồi make qa để nghe
	@echo "→ make qa"

all: extract tts mp3 daisy ## Chạy trọn bộ tới sách mở được + trang QA (chưa zip)

# ---------- Tiện ích ----------

thorium: daisy ## Nén sách thành zip và mở bằng Thorium Reader (Thorium không nhận .opf lẻ)
	@slug=$$($(PY) -c 'import json;print(json.load(open("metadata.json"))["slug"])'); \
	  rm -f out/$$slug-thorium.zip && (cd out/$$slug && zip -q -0 ../$$slug-thorium.zip *) && $(OPEN) -a Thorium out/$$slug-thorium.zip

voices: ## Sinh mẫu 25 giọng VieNeu vào build/thu-giong/ để chọn giọng
	$(PY) scripts/list_voices.py

validate: ## Kiểm XML well-formed bằng xmllint
	@cd out/$$($(PY) -c 'import json;print(json.load(open("metadata.json"))["slug"])') && \
	  for f in *.xml *.smil *.ncx *.opf *.res; do xmllint --noout "$$f" && echo "OK $$f"; done

clean-out: ## Xoá out/ (sinh lại bằng make daisy)
	rm -rf out

clean-mp3: ## Xoá mp3 + timing (giữ wav — sinh lại bằng make mp3, vài phút)
	rm -rf build/mp3 build/timing.json

clean-all: ## Xoá toàn bộ build/ và out/ — CẢ WAV (70 phút TTS)
	rm -rf build out

.PHONY: help qa submit-qa qa-check fetch merge-qa fix release setup check check-tts extract tts tts-groups mp3 daisy package trial all thorium voices validate clean-out clean-mp3 clean-all
