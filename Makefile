.PHONY: install dev test run run-brownfield run-ambiguous run-app clean

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest -q

# Mandatory use case, offline
run:
	python -m agentic_sdlc run --mock "Build a scalable URL shortener service with APIs, persistence, and analytics."

run-brownfield:
	python -m agentic_sdlc run --mock --file examples/brownfield_add_rate_limiting.md

run-ambiguous:
	python -m agentic_sdlc run --mock --file examples/ambiguous_make_it_better.md

# Start the GENERATED url-shortener (after a `make run`)
run-app:
	cd output && uvicorn app.main:app --reload

clean:
	rm -rf output .pytest_cache **/__pycache__ *.egg-info
