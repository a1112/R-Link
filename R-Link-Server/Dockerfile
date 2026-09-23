FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 rlink
COPY . .
RUN mkdir -p /data /app/logs /app/config /app/plugins && chown -R rlink:rlink /app /data
USER rlink
ENV R_LINK_HOST=0.0.0.0 R_LINK_DATA_DIR=/data/services R_LINK_DEVICES_DB=/data/devices.sqlite3 R_LINK_STORAGE_DIR=/data/shared
EXPOSE 8210
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8210/health', timeout=3)"
CMD ["python", "main.py"]
