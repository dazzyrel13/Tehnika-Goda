# Python 3.11 slim
FROM dockerhub.timeweb.cloud/library/python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-traditional \
    gcc \
    libpq-dev \
    gosu \
    && rm -rf /var/lib/apt/lists/* \
    && adduser --disabled-password --gecos "" appuser \
    && mkdir -p /usr/src/app/logs /usr/src/app/staticfiles /usr/src/app/media

COPY requirements.txt .
RUN pip install --upgrade pip setuptools && pip install -r requirements.txt

COPY entrypoint.sh .
RUN sed -i 's/\r$//' /usr/src/app/entrypoint.sh \
    && chmod +x /usr/src/app/entrypoint.sh

COPY . .
RUN sed -i 's/\r$//' /usr/src/app/entrypoint.sh \
    && chmod +x /usr/src/app/entrypoint.sh \
    && chown -R appuser:appuser /usr/src/app

ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
