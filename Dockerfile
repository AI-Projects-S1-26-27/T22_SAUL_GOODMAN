# Hosting config for the LIVE server (trials computed on request). Prepared, not deployed: see docs/process/DEPLOY.md.
# Build:  docker build -t saul-goodman-courtroom .
# Run:    docker run --rm -p 8000:8000 -e COURTROOM_ALLOWED_HOSTS=localhost saul-goodman-courtroom
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY courtroom ./courtroom
COPY results ./results
# an editable install keeps the voices, fonts and data next to the code (package-data lists only some of the web folder)
RUN pip install --no-cache-dir -e .

# no model key is set and none should be: the language-model layer stays off, and every route that would call a model answers 503
ENV PORT=8000 \
    COURTROOM_ALLOWED_HOSTS="" \
    PYTHONUNBUFFERED=1
EXPOSE 8000
# hosts such as Render and Fly.io pass the port in $PORT; set COURTROOM_ALLOWED_HOSTS to the public host name
CMD ["sh", "-c", "python -m courtroom serve --host 0.0.0.0 --port ${PORT:-8000}"]
