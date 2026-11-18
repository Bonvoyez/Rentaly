FROM python:3.12-slim

WORKDIR /app

# 라이브러리 먼저 설치 (코드만 바뀌면 이 단계는 캐시 재사용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
