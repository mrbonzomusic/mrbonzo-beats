#!/bin/sh
set -eu
ID="${1:-}"
SHORT="${2:-false}"
case "$ID" in
  *[!A-Za-z0-9_-]*|"")
    echo "invalid video id" >&2
    exit 1
    ;;
esac

WORKDIR="${WORKDIR:-/work}"
SRC="${WORKDIR}/reel-${ID}.src"
OUT="${WORKDIR}/reels-${ID}.mp4"
rm -f "$OUT" "${WORKDIR}/reel-${ID}.src."*

yt-dlp \
  -f "bv*[height<=1080]+ba/b[height<=1080]/b" \
  --extractor-args "youtube:player_client=android,ios,web" \
  --merge-output-format mp4 \
  -o "${SRC}.%(ext)s" \
  --no-playlist \
  --no-progress \
  --newline \
  "https://www.youtube.com/watch?v=${ID}"

IN="$(ls -1 "${WORKDIR}/reel-${ID}.src."* 2>/dev/null | head -n 1)"
if [ -z "$IN" ] || [ ! -f "$IN" ]; then
  echo "download missing" >&2
  exit 1
fi

VF="scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"

if [ "$SHORT" = "true" ] || [ "$SHORT" = "1" ]; then
  ffmpeg -y -hide_banner -loglevel error -i "$IN" -t 90 \
    -vf "$VF" -c:v libx264 -preset veryfast -crf 23 \
    -c:a aac -b:a 128k -movflags +faststart "$OUT"
else
  ffmpeg -y -hide_banner -loglevel error -ss 3 -t 18 -i "$IN" \
    -vf "$VF" -c:v libx264 -preset veryfast -crf 23 \
    -c:a aac -b:a 128k -movflags +faststart "$OUT"
fi

rm -f "$IN"
echo "$OUT"
