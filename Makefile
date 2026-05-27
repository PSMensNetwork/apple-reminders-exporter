# Detect the host OS so the right export method is used automatically
UNAME_S := $(shell uname -s)

all: save organize

# ── Save ──────────────────────────────────────────────────────────────────────
# macOS  → Shortcuts.app  (original method)
# Linux  → CalDAV fetcher (fetch_reminders.py)
ifeq ($(UNAME_S),Darwin)
.PHONY: save
save:
	mkdir -p reminders
	shortcuts run "Export Reminders" -i ./reminders
else
.PHONY: save
save:
	mkdir -p reminders
	python3 scripts/fetch_reminders.py --output ./reminders
endif

# ── Organize ──────────────────────────────────────────────────────────────────
.PHONY: organize
organize:
	python3 scripts/organize.py ./reminders

# ── Install dependencies (Linux only) ─────────────────────────────────────────
.PHONY: install
install:
ifeq ($(UNAME_S),Darwin)
	@echo "macOS: no extra Python dependencies required."
else
	pip3 install -r requirements.txt
endif

# ── Clean ─────────────────────────────────────────────────────────────────────
.PHONY: clean
clean:
	rm -rf ./reminders
