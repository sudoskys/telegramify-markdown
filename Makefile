.PHONY: adr-index adr-lint

adr-index:
	pdm run python scripts/adr-index.py --write

adr-lint:
	pdm run python scripts/adr-lint.py
