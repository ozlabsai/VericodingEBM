# Convenience commands. Run `make help` for the list.
# Uses .venv/bin/python directly to avoid uv's system-python fallback issues.

PY := .venv/bin/python

.PHONY: help test smoke-model smoke-data train install fmt

help:
	@echo "Commands:"
	@echo "  make install      - resolve deps with uv (writes .venv/)"
	@echo "  make test         - run unit tests (42 cases, ~6s on CPU)"
	@echo "  make smoke-model  - verify model wiring end-to-end on CPU (~30s)"
	@echo "  make smoke-data   - verify data pipeline on real files (needs data/raw/)"
	@echo "  make train        - launch training (needs GPU + data/raw/)"
	@echo ""
	@echo "Data files must live at:"
	@echo "  data/raw/system_trajectory_843.jsonl"
	@echo "  data/raw/sft_safe_25k.json"

install:
	uv sync --no-install-project
	uv pip install -e .

test:
	$(PY) -m pytest tests/ -p no:cacheprovider

smoke-model:
	$(PY) scripts/smoke_test_model.py

smoke-data:
	$(PY) scripts/smoke_test_data.py \
		--system-traj data/raw/system_trajectory_843.jsonl \
		--sft-safe    data/raw/sft_safe_25k.json

smoke-data-decoded:
	$(PY) scripts/smoke_test_data.py \
		--system-traj data/raw/system_trajectory_843.jsonl \
		--sft-safe    data/raw/sft_safe_25k.json \
		--show-decoded

train:
	$(PY) scripts/train.py --config configs/default.yaml
