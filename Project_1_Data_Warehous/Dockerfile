FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && groupadd --gid 10001 warehouse && useradd --uid 10001 --gid 10001 --no-create-home warehouse
COPY 1_Schema_Definition.sql 2_Sample_Data_Inserts.sql ./
COPY warehouse warehouse
COPY sql sql
COPY static static
RUN mkdir -p /app/runtime && chown warehouse:warehouse /app/runtime
USER warehouse
EXPOSE 8000
CMD ["sh", "-c", "python -m warehouse demo && exec python -m uvicorn warehouse.api:app --host 0.0.0.0 --port 8000"]
