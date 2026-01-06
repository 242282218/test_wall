FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# 默认改为你的 TMDB Key 或使用 docker run/docker compose 时传入环境变量
ENV TMDB_API_KEY=changeme

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7777"]

