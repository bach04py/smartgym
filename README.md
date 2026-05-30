# SmartGym — Realtime Heart Rate Dashboard

Quick instructions to run locally and deploy to Railway.

Requirements

Run locally
```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Run via script
```bash
sh run.sh
```

Deploy to Railway
1. Create a Railway project and connect your GitHub repo or push this repo to GitHub.
2. Use the included `Dockerfile` (recommended) or set the start command to: `sh run.sh` (Procfile is included).
	 - The `Dockerfile` uses `python:3.12-slim` which avoids compiling `pydantic-core` on newer Python versions where prebuilt wheels may not be available.
3. Ensure `requirements.txt` is present; Railway will install dependencies if you use the non-Docker approach.
4. Deploy — Railway will set `$PORT` automatically.

Docker (recommended)

Build and run locally with Docker:

```bash
docker build -t smartgym:latest .
docker run -p 8000:8000 -e PORT=8000 smartgym:latest
```

Notes about the pydantic build error

- If you see errors building `pydantic-core` (Rust compilation), it typically means the platform is using a Python version (e.g., 3.13) for which no binary wheel is available. The simplest fixes are:
	- Use Python 3.11 or 3.12 locally and in your deployment platform, or
	- Use the provided `Dockerfile` which pins to Python 3.12 and installs prebuilt wheels.
