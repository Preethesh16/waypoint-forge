#!/usr/bin/env bash
set -eo pipefail
# A dedicated virtual desktop keeps the simulation independent of the host OS.
export DISPLAY=${DISPLAY:-:99}
Xvfb "$DISPLAY" -screen 0 1600x900x24 -nolisten tcp &
XVFB_PID=$!
trap 'kill "$XVFB_PID" 2>/dev/null || true; jobs -pr | xargs -r kill' EXIT
ready=false
for _ in $(seq 1 50); do
    if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then ready=true; break; fi
    sleep 0.1
done
if ! "$ready"; then echo 'Virtual display did not become ready' >&2; exit 1; fi
openbox >/tmp/openbox.log 2>&1 &
x11vnc -display "$DISPLAY" -forever -shared -nopw -localhost -rfbport 5900 >/tmp/vnc.log 2>&1 &
# Docker must publish port 6080 to 127.0.0.1 only. The desktop has no password.
websockify --web=/usr/share/novnc 6080 localhost:5900 &
# Exit if any essential desktop process exits; the trap cleans up the rest.
status=0
wait -n || status=$?
if [ "$status" -eq 0 ]; then status=1; fi
exit "$status"
