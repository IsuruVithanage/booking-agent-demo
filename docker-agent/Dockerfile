FROM python:3.11-slim

WORKDIR /app
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ .

RUN useradd --create-home --shell /usr/sbin/nologin --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080
CMD ["python", "main.py"]
