#!/bin/bash
# Showcase Video Builder — configurable sections
# Usage: bash build_showcase.sh --images ./screenshots --output showcase.mp4

IMAGES_DIR="${1:-./screenshots}"
OUTPUT="${2:-showcase.mp4}"
DURATION=4
FPS=30
RES="1920x1080"
FONT="/System/Library/Fonts/Helvetica.ttc"
FFMPEG="${FFMPEG:-ffmpeg}"

# Build segments from all PNGs in order
i=0
FILTER=""
INPUTS=""
for img in "$IMAGES_DIR"/*.png; do
    [ -f "$img" ] || continue
    INPUTS="$INPUTS -loop 1 -t $DURATION -i $img"
    if [ $i -eq 0 ]; then
        FILTER="[$i:v]scale=${RES}:force_original_aspect_ratio=decrease,pad=${RES}:(ow-iw)/2:(oh-ih)/2,setsar=1,fade=t=out:st=$((DURATION-1)):d=1[v$i];"
    else
        FILTER="$FILTER [$i:v]scale=${RES}:force_original_aspect_ratio=decrease,pad=${RES}:(ow-iw)/2:(oh-ih)/2,setsar=1,fade=t=in:st=0:d=1,fade=t=out:st=$((DURATION-1)):d=1[v$i];"
    fi
    i=$((i+1))
done

# Concat
CONCAT=""
for j in $(seq 0 $((i-1))); do CONCAT="${CONCAT}[v$j]"; done

$FFMPEG $INPUTS -filter_complex "$FILTER ${CONCAT}concat=n=$i:v=1:a=0[out]" \
    -map "[out]" -c:v libx264 -pix_fmt yuv420p -r $FPS "$OUTPUT"

echo "✅ Built $OUTPUT from $i images"
