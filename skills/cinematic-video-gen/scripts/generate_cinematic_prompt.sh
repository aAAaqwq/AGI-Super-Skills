#!/usr/bin/env bash
set -euo pipefail

# Cinematic Prompt Generator
# 输入: 场景描述 → 输出: 五维灵动增强后的prompt

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 默认角色卡 (可被项目级覆盖)
CHARACTER=${CINEMATIC_CHARACTER:-""}
SCENE=${CINEMATIC_SCENE:-""}

usage() {
  cat <<'EOF'
Usage:
  CINEMATIC_CHARACTER="Chloe, young woman, long black hair with pink tips, white floral dress, cherry blossom hairpin" \
  ./generate_cinematic_prompt.sh "she rises from darkness into golden light" --emotion wonder --camera crane-up --motion "lifts chin slowly, fingers uncurl" --context "previous clip: dark void"

Options:
  --emotion EMO    Required emotion (wonder/melancholy/joy/serenity/determination/surprise)
  --camera TYPE    Camera movement (push-in/tracking/crane-up/orbit/handheld/pull-back)
  --motion DESC    Body movement description
  --context DESC   Connection to previous clip
  --character DESC Override character description
  --scene DESC     Scene/environment
  -o FILE          Output to file
EOF
}

EMOTION=""
CAMERA=""
MOTION=""
CONTEXT=""
OUTPUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --emotion) shift; EMOTION="$1" ;;
    --camera) shift; CAMERA="$1" ;;
    --motion) shift; MOTION="$1" ;;
    --context) shift; CONTEXT="$1" ;;
    --character) shift; CHARACTER="$1" ;;
    --scene) shift; SCENE="$1" ;;
    -o|--output) shift; OUTPUT="$1" ;;
    -h|--help) usage; exit 0 ;;
    *) DESC="$1" ;;
  esac
  shift
done

# 表情映射
declare -A EMOTION_MAP
EMOTION_MAP[wonder]="eyes widening with wonder, mouth forming a soft oh, face illuminated with sudden awe"
EMOTION_MAP[melancholy]="gazing into the distance with a melancholic longing, lips slightly parted, a hint of sadness in her deep eyes"
EMOTION_MAP[joy]="a warm genuine smile spreading across her face, eyes crinkling with pure happiness, radiating warmth"
EMOTION_MAP[serenity]="a peaceful serene expression, eyes half-closed in contentment, the softest smile playing on her lips"
EMOTION_MAP[determination]="jaw set with quiet determination, eyes blazing with inner strength, unwavering resolute gaze"
EMOTION_MAP[surprise]="eyebrows rising in delight, eyes sparkling with unexpected wonder, an involuntary gasp"
EMOTION_MAP[bittersweet]="a bittersweet smile forming, eyes glistening with unshed tears, lips trembling slightly"
EMOTION_MAP[release]="shoulders dropping with relief, a peaceful exhale visible, serene contentment washing over her face"
EMOTION_MAP[hope]="eyes lifting toward the light, a tentative smile forming, face softening with cautious optimism"

# 运镜映射
declare -A CAMERA_MAP
CAMERA_MAP[push-in]="Slow gentle push-in toward her face"
CAMERA_MAP[tracking]="Smooth tracking shot following her movement"
CAMERA_MAP[crane-up]="Slow crane-up shot rising from below"
CAMERA_MAP[orbit]="Orbiting 360 degrees around her"
CAMERA_MAP[handheld]="Intimate handheld close-up with subtle natural movement"
CAMERA_MAP[pull-back]="Steady pull-back revealing the full scene"
CAMERA_MAP[aerial]="Aerial drone shot descending toward her"

# 构建prompt
PROMPT=""

# 角色锚点
if [[ -n "$CHARACTER" ]]; then
  PROMPT+="[Character: $CHARACTER]\n\n"
fi

# 运镜 + 主体
if [[ -n "$CAMERA" ]]; then
  CAMERA_DESC="${CAMERA_MAP[$CAMERA]:-$CAMERA shot}"
  PROMPT+="$CAMERA_DESC: "
fi

# 场景描述
PROMPT+="${DESC:-she stands in contemplation}"

# 动作
if [[ -n "$MOTION" ]]; then
  PROMPT+=". She $MOTION"
fi

# 表情
if [[ -n "$EMOTION" ]]; then
  EMOTION_DESC="${EMOTION_MAP[$EMOTION]:-$EMOTION}"
  PROMPT+=". $EMOTION_DESC"
fi

# 场景环境
if [[ -n "$SCENE" ]]; then
  PROMPT+=". $SCENE"
fi

# 上下文衔接
if [[ -n "$CONTEXT" ]]; then
  PROMPT+=". $CONTEXT"
fi

# 质量后缀
PROMPT+=". Cinematic quality, 4K, shallow depth of field, natural motion blur, film grain, soft lighting."

if [[ -n "$OUTPUT" ]]; then
  echo -e "$PROMPT" > "$OUTPUT"
  echo "Prompt saved to: $OUTPUT"
else
  echo -e "$PROMPT"
fi
