#!/bin/bash
# Doble clic para abrir save-your-music: arranca el servidor y abre la página.
cd "$(dirname "$0")" || exit 1
(sleep 1 && open "http://localhost:8765") &
exec python3 server.py
