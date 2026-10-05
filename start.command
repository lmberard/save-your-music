#!/bin/bash
# Double-click to open save-your-music: starts the server and opens the page.
cd "$(dirname "$0")" || exit 1
(sleep 1 && open "http://localhost:8765") &
exec python3 server.py
