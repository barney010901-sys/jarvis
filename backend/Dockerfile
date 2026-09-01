# Build context is the REPO ROOT (see docker/docker-compose.yml), not
# backend/ — this image needs both backend/app and the top-level agent/
# package (the backend imports `agent.provider...`, not a vendored copy;
# see docs/DECISIONS.md, "Backend imports the agent package via
# PYTHONPATH, not packaging").
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app ./backend/app
COPY agent ./agent
COPY prompts ./prompts

# /app -> `agent` package; /app/backend -> `app` package.
ENV PYTHONPATH=/app:/app/backend
WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
