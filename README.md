# save-your-music

A local web page that turns YouTube or Spotify links into MP3 files.
Files come out in the format the Psier S18 player reads: constant 192 kbps MP3,
44.1 kHz, stereo, ID3v2.3 tags and a simple file name (`artist-title.mp3`).

<img width="1626" height="888" alt="Screenshot 2026-10-05 at 3 53 45 PM" src="https://github.com/user-attachments/assets/a56f2cf5-1278-4f1e-a4bf-1194f67728f6" />
<img width="1637" height="703" alt="Screenshot 2026-10-05 at 3 53 27 PM" src="https://github.com/user-attachments/assets/aca2dd8e-658a-48e1-880b-be0fe7073e70" />


## How to use it

Double-click `start.command`. It opens a Terminal window running the server and
the page in your browser (`http://localhost:8765`). To stop it, close that
Terminal window or press Ctrl+C.

From the terminal:

```bash
python3 server.py
```

Paste one or more links into the page (one per line) and each MP3 is downloaded
to your browser's Downloads folder.

## What it accepts

- YouTube links (`youtube.com`, `youtu.be`, `music.youtube.com`). Only that
  video is downloaded, never the whole playlist.
- Spotify track links. Spotify audio cannot be downloaded: the title, artist and
  duration are read from the link, the track is looked up on YouTube and
  downloaded from there.
- Spotify albums and playlists are not supported from the page.

## Requirements

`yt-dlp` and `ffmpeg` installed with Homebrew, and Python 3 (the one that ships
with macOS is enough):

```bash
brew install yt-dlp ffmpeg
```

If YouTube starts rejecting downloads, updating almost always fixes it:

```bash
brew upgrade yt-dlp
```

## Structure

- `server.py`: local server (only answers requests from this machine, port 8765).
- `static/index.html`: the page.
- `scripts/`: download and conversion logic (`yt_mp3.sh`, `spotify_mp3.py`, `slug.py`).

This is a local tool: it is not meant to be published on the internet.
