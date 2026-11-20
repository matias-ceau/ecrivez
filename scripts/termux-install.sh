#!/bin/sh
# Install ecrivez-web on an Android phone, inside Termux (the F-Droid build).
# Everything stays in Termux's private storage: no other app can read it.
# Safe to run again: it updates the program and keeps the key, the code and the data.
set -eu

BRANCH="${ECRIVEZ_BRANCH:-main}"
DATA="$HOME/ecrivez"
CONF="$HOME/.config/ecrivez"
ENV_FILE="$CONF/env"
START="$HOME/.local/bin/ecrivez-phone"

pkg update -y
pkg install -y python ffmpeg uv
uv tool install --force "ecrivez @ https://github.com/matias-ceau/ecrivez/archive/refs/heads/$BRANCH.tar.gz"

mkdir -p "$DATA" "$CONF" "$HOME/.local/bin"
if [ ! -s "$ENV_FILE" ]; then
    printf "Colle la clé OpenRouter puis Entrée (elle ne s'affiche pas) : "
    stty -echo < /dev/tty
    read -r KEY < /dev/tty
    stty echo < /dev/tty
    echo
    umask 077
    {
        echo "OPENROUTER_API_KEY=$KEY"
        echo "ECRIVEZ_DRAFT_MODEL=anthropic/claude-opus-5.5"
        echo "ECRIVEZ_DATA=$DATA"
    } > "$ENV_FILE"
fi

cat > "$START" <<'LAUNCH'
#!/bin/sh
# Start the server unless it already runs; keep the phone from putting Termux to sleep.
PID="$HOME/.config/ecrivez/pid"
if [ -s "$PID" ] && grep -q ecrivez-web "/proc/$(cat "$PID")/cmdline" 2> /dev/null; then
    exit 0
fi
set -a
. "$HOME/.config/ecrivez/env"
set +a
termux-wake-lock
nohup "$HOME/.local/bin/ecrivez-web" >> "$HOME/.config/ecrivez/journal.txt" 2>&1 &
echo $! > "$PID"
LAUNCH
chmod +x "$START"

# Opening Termux is enough to have the server running.
grep -q ecrivez-phone "$HOME/.bashrc" 2> /dev/null || echo "$START" >> "$HOME/.bashrc"

# After an update, the server already running is the old program: replace it.
if [ -s "$CONF/pid" ] && grep -q ecrivez-web "/proc/$(cat "$CONF/pid")/cmdline" 2> /dev/null; then
    kill "$(cat "$CONF/pid")" || true
    sleep 1
fi
"$START"
sleep 3
echo
echo "Installé. Ouvre http://127.0.0.1:8377 dans Chrome et tape ce code (une seule fois) :"
cat "$DATA/web-code"
echo "Puis menu de Chrome > Ajouter à l'écran d'accueil."
