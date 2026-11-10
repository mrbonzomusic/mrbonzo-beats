FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates fonts-dejavu-core \
 && pip install --no-cache-dir yt-dlp \
 && rm -rf /var/lib/apt/lists/*

COPY reel-prep.sh short-prep.sh reel-server.py /usr/local/bin/
# Τα αρχεία από Windows έχουν CRLF· αφαιρούνται ώστε να τρέχουν τα shell scripts
RUN sed -i 's/\r$//' /usr/local/bin/reel-prep.sh /usr/local/bin/short-prep.sh /usr/local/bin/reel-server.py \
 && chmod 755 /usr/local/bin/reel-prep.sh /usr/local/bin/short-prep.sh /usr/local/bin/reel-server.py

WORKDIR /work
EXPOSE 8080
CMD ["python3", "/usr/local/bin/reel-server.py"]
