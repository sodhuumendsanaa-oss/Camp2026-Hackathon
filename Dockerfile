FROM python:3.9-slim

WORKDIR /app

# 依存パッケージのインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ソースコードのコピー
COPY . .

# Hugging Face Spaces はポート 7860 でリスンする必要があります
EXPOSE 7860

# アプリケーションの起動
CMD ["gunicorn", "-b", "0.0.0.0:7860", "app:app"]
