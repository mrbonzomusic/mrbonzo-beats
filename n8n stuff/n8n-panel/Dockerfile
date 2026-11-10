FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && pip install --no-cache-dir yt-dlp \
 && rm -rf /var/lib/apt/lists/*

COPY app.py workflow_patch.py captions.py campaigns.py uploader.py uploader_ui.py /opt/panel/
RUN sed -i 's/\r$//' /opt/panel/app.py /opt/panel/workflow_patch.py /opt/panel/captions.py /opt/panel/campaigns.py /opt/panel/uploader.py /opt/panel/uploader_ui.py

WORKDIR /opt/panel
EXPOSE 8080
CMD ["python3", "/opt/panel/app.py"]
