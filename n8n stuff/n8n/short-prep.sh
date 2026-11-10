#!/bin/sh
# short-prep.sh <videoId> [start|auto] [seconds]
# Κατεβάζει το βίντεο και φτιάχνει κάθετο 1080x1920 κλιπ για YouTube Short (θολό φόντο, το βίντεο στη μέση).
set -eu
ID="${1:-}"
START="${2:-auto}"
SECS="${3:-30}"
case "$ID" in
  *[!A-Za-z0-9_-]*|"") echo "invalid video id" >&2; exit 1 ;;
esac
case "$SECS" in
  ""|*[!0-9]*) echo "invalid seconds" >&2; exit 1 ;;
esac
case "$START" in
  auto) ;;
  ""|*[!0-9]*) echo "invalid start" >&2; exit 1 ;;
esac
if [ "$SECS" -lt 5 ] || [ "$SECS" -gt 170 ]; then
  echo "seconds must be 5-170" >&2
  exit 1
fi

WORKDIR="${WORKDIR:-/work}"
SRC="${WORKDIR}/ytshort-${ID}.src"
OUT="${WORKDIR}/ytshort-${ID}.mp4"
rm -f "$OUT" "${SRC}."*

yt-dlp \
  -f "bv*[height<=1080]+ba/b[height<=1080]/b" \
  --extractor-args "youtube:player_client=android,ios,web" \
  --merge-output-format mp4 \
  -o "${SRC}.%(ext)s" \
  --no-playlist \
  --no-progress \
  --newline \
  "https://www.youtube.com/watch?v=${ID}"

IN="$(ls -1 "${WORKDIR}/ytshort-${ID}.src."* 2>/dev/null | head -n 1)"
if [ -z "$IN" ] || [ ! -f "$IN" ]; then
  echo "download missing" >&2
  exit 1
fi

DUR="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$IN" 2>/dev/null | cut -d. -f1)"
case "$DUR" in
  ""|*[!0-9]*) DUR=0 ;;
esac

if [ "$START" = "auto" ]; then
  START=$((DUR * 30 / 100))
fi
if [ "$DUR" -gt 0 ]; then
  MAXSTART=$((DUR - SECS))
  if [ "$MAXSTART" -lt 0 ]; then MAXSTART=0; fi
  if [ "$START" -gt "$MAXSTART" ]; then START=$MAXSTART; fi
fi

FC="[0:v]split=2[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:10[bg];[b]scale=w=1080:h=1920:force_original_aspect_ratio=decrease:force_divisible_by=2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]"

# Κείμενο πάνω στο βίντεο (προαιρετικό): HOOK πάνω, CTA κάτω. Γράφονται σε αρχεία ώστε να μην υπάρχουν θέματα escaping.
FONT="${FONT:-/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf}"
TXT="${WORKDIR}/ytshort-${ID}.txt"
rm -f "${TXT}.hook" "${TXT}.cta"
if [ -f "$FONT" ]; then
  if [ -n "${HOOK:-}" ]; then
    printf '%s' "$HOOK" > "${TXT}.hook"
    FC="${FC},drawtext=fontfile=${FONT}:textfile=${TXT}.hook:fontsize=${HOOK_FS:-96}:fontcolor=white:borderw=7:bordercolor=black:x=(w-text_w)/2:y=250"
  fi
  if [ -n "${CTA:-}" ]; then
    printf '%s' "$CTA" > "${TXT}.cta"
    FC="${FC},drawtext=fontfile=${FONT}:textfile=${TXT}.cta:fontsize=${CTA_FS:-60}:fontcolor=yellow:borderw=5:bordercolor=black:x=(w-text_w)/2:y=h-330"
  fi
fi
# το drawtext μπαίνει πριν το [v]: ξαναβάζουμε την ετικέτα εξόδου
FC="$(printf '%s' "$FC" | sed 's/,format=yuv420p\[v\]//')"
FC="${FC},format=yuv420p[v]"

ffmpeg -y -hide_banner -loglevel error -ss "$START" -t "$SECS" -i "$IN" \
  -filter_complex "$FC" -map "[v]" -map "0:a?" \
  -c:v libx264 -preset veryfast -crf 23 -r 30 \
  -c:a aac -b:a 128k -movflags +faststart "$OUT"

rm -f "$IN" "${TXT}.hook" "${TXT}.cta"
echo "$OUT"
