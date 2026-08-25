FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DATA_DIR=/data
WORKDIR /app
RUN addgroup --system panel && adduser --system --ingroup panel panel && mkdir -p /data && chown -R panel:panel /data
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=panel:panel . .
USER panel
EXPOSE 8080
CMD ["sh","-c","uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
