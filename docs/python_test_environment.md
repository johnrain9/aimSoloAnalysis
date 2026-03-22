# Reproducible Python Test Environment

This repository now defines pinned dependencies for runtime and tests:

- `pyproject.toml` (project metadata + pytest defaults)
- `requirements.txt` (runtime dependencies)
- `requirements-dev.txt` (runtime + test dependencies)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Run tests

```bash
python -m pytest
```

`pytest` is pinned so local and CI test behavior can be recreated from source control.
