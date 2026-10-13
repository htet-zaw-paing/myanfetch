FROM python:3.10-slim

RUN apt-get update && apt-get install -y ffmpeg nodejs

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -U https://github.com/yt-dlp/yt-dlp/archive/master.zip

COPY . .

CMD ["python", "bot.py"]
