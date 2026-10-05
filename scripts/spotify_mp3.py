#!/usr/bin/env python3
"""Downloads songs from a Spotify link.

Spotify audio cannot be downloaded: the title, artist and duration are read
from the link's public page, the track is looked up on YouTube and downloaded
from there with yt_mp3.sh. The final file is named "artist-title.mp3".

Usage:
  spotify_mp3.py <spotify_link> [output_dir]          # one track
  spotify_mp3.py --list <spotify_link>                # list the tracks of an album/playlist
  spotify_mp3.py --all <spotify_link> [output_dir]    # download a whole album/playlist
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

from slug import slug

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.expanduser("~/Music/Psier-S18")
UA = {"User-Agent": "Mozilla/5.0"}
# Versions we don't want unless the original track already says so in its title.
UNWANTED = ["live", "en vivo", "cover", "remix", "sped up", "slowed", "8d",
            "karaoke", "instrumental", "nightcore", "reverb", "extended", "mix"]


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.geturl(), r.read().decode("utf-8", "replace")


def parse_link(url):
    if "spotify.link" in url:  # short link: follow the redirect
        url, _ = fetch(url)
    m = re.search(r"spotify[:.].*?(track|album|playlist)[/:]([A-Za-z0-9]{22})", url)
    if not m:
        sys.exit(f"Unrecognized Spotify link: {url}")
    return m.group(1), m.group(2)


def entity(kind, sid):
    _, html = fetch(f"https://open.spotify.com/embed/{kind}/{sid}")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        sys.exit("Spotify changed its page format; could not read the track data.")
    return json.loads(m.group(1))["props"]["pageProps"]["state"]["data"]["entity"]


def tracks(kind, sid):
    """List of (artist, title, duration_in_seconds)."""
    e = entity(kind, sid)
    if kind == "track":
        artist = ", ".join(a["name"] for a in e.get("artists", []))
        return e.get("name", sid), [(artist, e["name"], e["duration"] / 1000)]
    out = [(t.get("subtitle", ""), t["title"], t["duration"] / 1000)
           for t in e.get("trackList", []) if t.get("entityType", "track") == "track"]
    return e.get("name", sid), out


def find_on_youtube(artist, title, duration):
    query = f"ytsearch8:{artist} {title}"
    res = subprocess.run(
        ["yt-dlp", "--flat-playlist", "--no-warnings", "--print",
         "%(id)s\t%(duration)s\t%(channel)s\t%(title)s", query],
        capture_output=True, text=True)
    wanted = f"{artist} {title}".lower()
    best = None
    for pos, line in enumerate(res.stdout.splitlines()):
        parts = line.split("\t")
        if len(parts) != 4 or not parts[1].replace(".", "").isdigit():
            continue
        vid, dur, channel, vtitle = parts[0], float(parts[1]), parts[2], parts[3]
        diff = abs(dur - duration)
        score = diff + pos  # on a tie, keep YouTube's own order
        low = vtitle.lower()
        if channel.endswith("- Topic") or "official audio" in low:
            score -= 5  # studio audio, without a music video's intro/outro
        for word in UNWANTED:
            if re.search(rf"\b{re.escape(word)}\b", low) and not re.search(rf"\b{re.escape(word)}\b", wanted):
                score += 30
        if title.lower().split("(")[0].strip() not in low:
            score += 30
        if best is None or score < best[0]:
            best = (score, vid, diff, channel, vtitle)
    return best


def download(artist, title, duration, out_dir):
    name = (slug(f"{artist} - {title}") or slug(title) or "track") + ".mp3"
    final = os.path.join(out_dir, name)
    if os.path.exists(final):
        print(f"Already exists, not overwritten: {final}")
        return final
    best = find_on_youtube(artist, title, duration)
    if best is None:
        print(f"ERROR: not found on YouTube: {artist} - {title}", file=sys.stderr)
        return None
    _, vid, diff, channel, vtitle = best
    print(f"{artist} - {title}  ->  YouTube: {vtitle} [{channel}] (duration difference: {diff:.0f}s)")
    if diff > 15:
        print("  WARNING: the duration does not match; this may be a different version of the track.",
              file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        res = subprocess.run([os.path.join(HERE, "yt_mp3.sh"), f"https://www.youtube.com/watch?v={vid}", tmp],
                             capture_output=True, text=True)
        files = [f for f in os.listdir(tmp) if f.endswith(".mp3")]
        if res.returncode != 0 or not files:
            print(f"ERROR downloading {artist} - {title}:\n{res.stderr.strip()[-500:]}", file=sys.stderr)
            return None
        # Replace the YouTube tags with Spotify's, without re-encoding.
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", os.path.join(tmp, files[0]),
             "-map", "0:a", "-c", "copy", "-map_metadata", "-1", "-map_chapters", "-1",
             "-metadata", f"title={title}", "-metadata", f"artist={artist}",
             "-id3v2_version", "3", "-write_id3v1", "1", final],
            check=True)
    print(final)
    return final


def main():
    args = sys.argv[1:]
    mode = "one"
    if args and args[0] in ("--list", "--all"):
        mode = args.pop(0)[2:]
    if not args:
        sys.exit(__doc__)
    out_dir = args[1] if len(args) > 1 else DEFAULT_OUT
    kind, sid = parse_link(args[0])
    name, items = tracks(kind, sid)

    if mode == "list":
        print(f"{kind}: {name} ({len(items)} tracks)")
        for i, (artist, title, dur) in enumerate(items, 1):
            print(f"{i:3}. {artist} - {title} ({int(dur // 60)}:{int(dur % 60):02})")
        return
    if kind != "track" and mode != "all":
        sys.exit(f"The link is a {kind} with {len(items)} tracks ({name}). "
                 "Use --list to see them and --all to download them all.")

    os.makedirs(out_dir, exist_ok=True)
    failed = [f"{a} - {t}" for a, t, d in items if download(a, t, d, out_dir) is None]
    if failed:
        sys.exit("Could not download: " + "; ".join(failed))


if __name__ == "__main__":
    main()
