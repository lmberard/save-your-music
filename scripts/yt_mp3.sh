#!/bin/bash
# Descarga el audio de un link de YouTube como MP3 compatible con el Psier S18.
# Uso: yt_mp3.sh <url> [carpeta_destino]
set -euo pipefail

URL="${1:?Uso: yt_mp3.sh <url> [carpeta_destino]}"
OUT_DIR="${2:-$HOME/Music/Psier-S18}"

# Los links de Spotify se resuelven aparte (busca el tema en YouTube y vuelve a llamar a este script).
if [[ "$URL" == *spotify* ]]; then
  exec python3 "$(dirname "$0")/spotify_mp3.py" "$@"
fi

for bin in yt-dlp ffmpeg; do
  command -v "$bin" >/dev/null || { echo "Falta $bin (brew install $bin)" >&2; exit 1; }
done

mkdir -p "$OUT_DIR"

# Nombre de archivo simple (minúsculas, sin acentos ni símbolos), que el reproductor muestra bien.
TITLE="$(yt-dlp --no-playlist --no-warnings --print "%(title)s" "$URL")"
NAME="$(python3 "$(dirname "$0")/slug.py" "$TITLE")"
[ -n "$NAME" ] || NAME="$(yt-dlp --no-playlist --no-warnings --print "%(id)s" "$URL")"
if [ -e "$OUT_DIR/$NAME.mp3" ]; then
  echo "Ya existe, no se sobreescribe: $OUT_DIR/$NAME.mp3"
  exit 0
fi

# MP3 CBR 192 kbps, 44.1 kHz, estéreo, tags ID3v2.3 y sin carátula embebida:
# es la combinación que los reproductores chinos genéricos leen sin trabarse.
# --http-chunk-size evita el HTTP 403 que YouTube devuelve a descargas sin trocear.
# Aun así YouTube a veces responde 403 de forma transitoria, por eso se reintenta.
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
  [ "$attempt" -lt 3 ] && { echo "Falló el intento $attempt, reintentando..." >&2; sleep 3; }
done
exit 1
