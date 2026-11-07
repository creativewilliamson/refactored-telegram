# VetsEatFree: Python pipeline + static site generator + plain static server.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY pipeline ./pipeline
COPY tests ./tests

EXPOSE 8095
CMD ["python", "-m", "pipeline.serve", "--dir", "dist", "--port", "8095"]
