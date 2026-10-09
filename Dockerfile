FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py prompt_loader.py ./
COPY prompts ./prompts

# Run as a non-root user
RUN useradd --create-home appuser
USER appuser

# Cloud Run sets PORT; default to 8080 for local `docker run`
ENV HOST=0.0.0.0 PORT=8080
EXPOSE 8080

CMD ["python", "main.py"]
