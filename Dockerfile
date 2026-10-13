FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg curl

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir -U https://github.com/yt-dlp/yt-dlp/archive/master.zip

COPY . .

CMD ["python", "bot.py"]