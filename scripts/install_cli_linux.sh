#!/bin/bash
# Installs a `meeting-agent` command on PATH (~/.local/bin) that runs this
# checkout's .venv regardless of current directory. Run it, and if config
# is incomplete it opens the Settings dialog (Gemini key, SMTP, R2, etc.).
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "No .venv found at $PROJECT_DIR/.venv -- run this first:" >&2
    echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    exit 1
fi

mkdir -p ~/.local/bin
cat > ~/.local/bin/meeting-agent << EOF
#!/bin/bash
# meeting_agent is a local package, not pip-installed -- must run with the
# project dir as cwd so "-m meeting_agent" can find it regardless of where
# this command is invoked from.
cd "$PROJECT_DIR"
exec "$VENV_PYTHON" -m meeting_agent "\$@"
EOF
chmod +x ~/.local/bin/meeting-agent

echo "Installed: ~/.local/bin/meeting-agent"
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$HOME/.local/bin"; then
    echo "NOTE: $HOME/.local/bin is not on your PATH -- add this to your shell rc:"
    echo '  export PATH="$HOME/.local/bin:$PATH"'
else
    echo "Run it: meeting-agent"
fi
