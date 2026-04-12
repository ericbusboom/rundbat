FROM python:3.12-slim
WORKDIR /app

COPY requirements*.txt pyproject.toml* ./
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null \
    || pip install --no-cache-dir . 2>/dev/null \
    || true
COPY . .

EXPOSE ${PORT:-8000}
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
