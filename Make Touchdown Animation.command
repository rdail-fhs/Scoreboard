#!/bin/bash
# Double-click: make the Broadcast v2 touchdown animation for a new team.
cd "$(dirname "$0")"
B=/Applications/Blender.app/Contents/MacOS/Blender
ask() { osascript -e "text returned of (display dialog \"$1\" default answer \"$2\" with title \"Touchdown Animation\")" 2>/dev/null; }

NAME=$(ask "Team name for the plate under TOUCHDOWN (example: PIRATES)" "") || exit 0
[ -z "$NAME" ] && exit 0
COLOR=$(ask "Team color as a hex code (example: #003cc7)" "#") || exit 0
LOGO=$(osascript -e 'POSIX path of (choose file with prompt "Choose the team logo (a PNG with a transparent background works best)" of type {"public.image"})' 2>/dev/null) || exit 0

SLUG=$(echo "$NAME" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-*//; s/-*$//')
EXT=$(echo "${LOGO##*.}" | tr '[:upper:]' '[:lower:]')
mkdir -p assets/anim
cp "$LOGO" "assets/$SLUG.$EXT"
OUT="assets/anim/$SLUG-td.webm"

echo ""
echo "  Rendering the $NAME touchdown animation. This takes a few minutes..."
echo ""
"$B" -b blender/touchdown_template.blend --python blender/make_touchdown.py -- \
  --name "$NAME" --color "$COLOR" --logo "assets/$SLUG.$EXT" --out "$OUT" 2>&1 | grep -E "\[touchdown\]|Error"

if [ ! -s "$OUT" ]; then
  osascript -e 'display alert "Render failed" message "Check the Terminal window for errors."' >/dev/null
  exit 1
fi

CHOICE=$(osascript -e "button returned of (display dialog \"Done! Saved $OUT\n\nPublish it to the website now?\" buttons {\"Not now\", \"Publish\"} default button \"Publish\" with title \"Touchdown Animation\")" 2>/dev/null)
if [ "$CHOICE" = "Publish" ]; then
  git add "assets/$SLUG.$EXT" "$OUT" && git commit -qm "Add $NAME logo and touchdown animation" && git push -q && echo "  Published."
fi

osascript -e "display dialog \"Last step, in the controller under Team & game setup for this team:\n\nLogo:  assets/$SLUG.$EXT\nTouchdown animation video:  $OUT\n\n(It's live about a minute after publishing.)\" buttons {\"OK\"} with title \"Touchdown Animation\"" >/dev/null
