#!/bin/bash
# Double-click to start the scoreboard server on this Mac.
cd "$(dirname "$0")"
(sleep 1.5; open "http://localhost:8765/control/") &
python3 server.py
