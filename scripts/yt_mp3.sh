#!/bin/bash
# Downloads the audio of a YouTube link as an MP3 the Psier S18 can play.
# Usage: yt_mp3.sh <url> [output_dir]
set -euo pipefail

URL="${1:?Usage: yt_mp3.sh <url> [output_dir]}"
OUT_DIR="${2:-$HOME/Music/Psier-S18}"

# Spotify links are resolved separately (the track is looked up on YouTube and this script is called again).
if [[ "$URL" == *spotify* ]]; then
  exec python3 "$(dirname "$0")/spotify_mp3.py" "$@"
fi

for bin in yt-dlp ffmpeg; do
  command -v "$bin" >/dev/null || { echo "Missing $bin (brew install $bin)" >&2; exit 1; }
done

mkdir -p "$OUT_DIR"

# Simple file name (lowercase, no accents or symbols) that the player displays correctly.
TITLE="$(yt-dlp --no-playlist --no-warnings --print "%(title)s" "$URL")"
NAME="$(python3 "$(dirname "$0")/slug.py" "$TITLE")"
[ -n "$NAME" ] || NAME="$(yt-dlp --no-playlist --no-warnings --print "%(id)s" "$URL")"
if [ -e "$OUT_DIR/$NAME.mp3" ]; then
  echo "Already exists, not overwritten: $OUT_DIR/$NAME.mp3"
  exit 0
fi

# CBR 192 kbps MP3, 44.1 kHz, stereo, ID3v2.3 tags and no embedded cover art:
# the combination generic players read without choking.
# --http-chunk-size avoids the HTTP 403 YouTube returns for unchunked downloads.
# YouTube still answers 403 transiently now and then, hence the retries.
for attempt in 1 2 3; do
  yt-dlp \
  --no-playlist \
  --format "bestaudio/best" \
  --http-chunk-size 10M \
  --extract-audio \
  --audio-format mp3 \
  --audio-quality 192K \
  --postprocessor-args "ExtractAudio:-ar 44100 -ac 2" \
  --embed-metadata \
  --parse-metadata "%(artist,uploader)s:%(meta_artist)s" \
  --postprocessor-args "Metadata:-id3v2_version 3 -write_id3v1 1" \
  --no-overwrites \
  --output "$OUT_DIR/$NAME.%(ext)s" \
  --print after_move:filepath \
  --no-simulate \
  --quiet --no-warnings --progress \
  "$URL" && exit 0
  [ "$attempt" -lt 3 ] && { echo "Attempt $attempt failed, retrying..." >&2; sleep 3; }
done
exit 1
