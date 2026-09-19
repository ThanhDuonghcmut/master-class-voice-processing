# Sách nói DAISY 3 — Những tấm lòng cao cả.  `make help` để xem lệnh.
# Mọi target chạy trong .venv của repo (tạo bằng `make setup`). Windows không có make: xem README, chạy thẳng scripts/*.py.

PY      ?= .venv/bin/python
GROUPS  ?= front lv1-02 lv2-001 notes   # nhóm dùng cho `make trial`; xem id trong build/book.json
SHELL   := /bin/bash

.DEFAULT_GOAL := help

help: ## Liệt kê lệnh
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Tạo .venv + cài thư viện bằng Python có sẵn; Python không phải 3.10–3.13 thì tự cài uv và tải 3.12
	python3 scripts/setup.py

check: ## Kiểm tra máy: Python, thư viện, RAM, đĩa, cache model
	$(PY) scripts/00_check_env.py

check-tts: ## Như check + tải model và đọc thử 1 câu để đo tốc độ
	$(PY) scripts/00_check_env.py --tts

extract: ## Bước 1: PDF → build/book.json
	$(PY) scripts/01_extract_pdf.py

tts: ## Bước 2: đọc CẢ SÁCH (~70 phút trên M5 Pro; chạy lại được, bỏ qua wav đã có)
	$(PY) scripts/02_tts.py

tts-groups: ## Bước 2 cho vài nhóm: make tts-groups GROUPS="lv2-001 lv2-002"
	$(PY) scripts/02_tts.py $(GROUPS)

mp3: ## Bước 3: ghép wav → mp3 + timing.json (nhóm nào đủ wav mới ghép)
	$(PY) scripts/03_concat_mp3.py

daisy: ## Bước 4: sinh dtbook/smil/ncx/opf → out/<slug>/ (mở bằng Thorium Reader)
	$(PY) scripts/04_build_daisy.py

package: ## Bước 5: bản nộp — kiểm metadata đủ, zip + sha256 vào out/<MSHV>/
	$(PY) scripts/04_build_daisy.py --strict
	$(PY) scripts/05_package.py

trial: extract tts-groups mp3 daisy ## Dựng thử nhanh (~3 phút): tên sách + THÁNG MƯỜI + Ngày khai trường + chú thích
	@echo "→ Mở out/*/package.opf bằng Thorium Reader để nghe thử"

all: extract tts mp3 daisy ## Chạy trọn bộ tới sách mở được (chưa zip)

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

.PHONY: help setup check check-tts extract tts tts-groups mp3 daisy package trial all voices validate clean-out clean-mp3 clean-all
