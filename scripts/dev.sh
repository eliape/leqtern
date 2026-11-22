#!/usr/bin/env bash
# Start the backend (port 8000) and the frontend dev server (port 5173) together.
# If either one stops, the other is stopped too. Ctrl+C stops both.
# Written for the bash 3.2 that ships with macOS (no `wait -n`).
set -uo pipefail
cd "$(dirname "$0")/.."

BACKEND_PORT=8000

say() { echo "dev.sh: $*" >&2; }

# Fail before starting anything if the backend's port is taken, usually by an
# earlier run that is still alive. One that was just told to stop takes a moment
# to shut down and let go of the port, so give it a few seconds first.
port_taken() { (exec 3<>"/dev/tcp/127.0.0.1/$BACKEND_PORT") 2>/dev/null; }
for _ in 1 2 3 4 5 6 7 8 9 10; do
  port_taken || break
  sleep 0.5
done
if port_taken; then
  say "port $BACKEND_PORT is already in use, probably by an earlier run of the backend."
  say "see what holds it:  lsof -i :$BACKEND_PORT"
  say "stop it:            lsof -ti :$BACKEND_PORT | xargs kill"
  exit 1
fi

# Run each server in its own process group so it can be stopped with everything
# it spawned (uv -> uvicorn reloader -> worker, npm -> vite). Their stdin is
# /dev/null because a background process group that reads the terminal is
# suspended.
set -m
(cd backend && exec uv run uvicorn leqtern.main:app --reload --port "$BACKEND_PORT") </dev/null &
backend_pid=$!
(cd frontend && exec npm run dev) </dev/null &
frontend_pid=$!
set +m

stop_all() {
  trap - INT TERM EXIT
  kill -TERM -- "-$backend_pid" "-$frontend_pid" 2>/dev/null
  wait 2>/dev/null
}
trap 'stop_all; exit 130' INT
trap 'stop_all; exit 143' TERM
# Closing the terminal (or its tab) sends HUP. Without this the servers, each in
# its own process group, would outlive it and keep the port.
trap 'stop_all; exit 129' HUP
trap stop_all EXIT

while kill -0 "$backend_pid" 2>/dev/null && kill -0 "$frontend_pid" 2>/dev/null; do
  sleep 1
done

if ! kill -0 "$backend_pid" 2>/dev/null; then
  say "the backend stopped, so the frontend is being stopped too. See the error above."
else
  say "the frontend stopped, so the backend is being stopped too. See the error above."
fi
exit 1
