FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cached layer unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Railway sets PORT env var
CMD ["gunicorn", "run_review:app", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120"]
