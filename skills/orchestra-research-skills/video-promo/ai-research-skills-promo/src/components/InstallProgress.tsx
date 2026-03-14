import React from "react";
import {
  interpolate,
  useCurrentFrame,
  useVideoConfig,
  spring,
  Easing,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/JetBrainsMono";

const { fontFamily: monoFont } = loadFont();

const COLORS = {
  green: "#3fb950",
  cyan: "#58a6ff",
  yellow: "#d29922",
  dim: "#8b949e",
  text: "#e6edf3",
  bg: "#161b22",
};

const SKILL_NAMES = [
  "grpo-rl-training",
  "verl",
  "slime",
  "vllm",
  "sglang",
  "deepspeed",
  "flash-attention",
  "axolotl",
  "unsloth",
  "wandb",
  "lm-eval-harness",
  "dspy",
  "ml-paper-writing",
];

type InstallProgressProps = {
  startDelay?: number;
};

export const InstallProgress: React.FC<InstallProgressProps> = ({
  startDelay = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const adjustedFrame = Math.max(0, frame - startDelay);

  // Progress bar animation - 1 second for full progress (scene is 1.25s total at 4x speed)
  const progressDuration = 1 * fps;
  const progress = interpolate(adjustedFrame, [0, progressDuration], [0, 100], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  // Spinning indicator
  const spinnerChars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];
  const spinnerIndex = Math.floor(adjustedFrame / 3) % spinnerChars.length;
  const spinner = progress < 100 ? spinnerChars[spinnerIndex] : "✓";

  // Current skill being installed
  const skillIndex = Math.min(
    SKILL_NAMES.length - 1,
    Math.floor((progress / 100) * SKILL_NAMES.length)
  );
  const currentSkill = SKILL_NAMES[skillIndex];

  // Installed count
  const installedCount = Math.floor((progress / 100) * 82);

  // Fade in
  const fadeIn = spring({
    frame: adjustedFrame,
    fps,
    config: { damping: 200 },
  });

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 24,
        opacity: fadeIn,
        fontFamily: monoFont,
      }}
    >
      {/* Installing header */}
      <div
        style={{
          fontSize: 18,
          color: COLORS.cyan,
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <span style={{ color: progress < 100 ? COLORS.yellow : COLORS.green }}>
          {spinner}
        </span>
        <span>
          {progress < 100
            ? `Installing skills to 5 agents...`
            : `Installation complete!`}
        </span>
      </div>

      {/* Progress bar */}
      <div
        style={{
          width: "100%",
          height: 8,
          backgroundColor: COLORS.bg,
          borderRadius: 4,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${progress}%`,
            height: "100%",
            backgroundColor: progress < 100 ? COLORS.cyan : COLORS.green,
            borderRadius: 4,
          }}
        />
      </div>

      {/* Current skill */}
      <div
        style={{
          fontSize: 16,
          color: COLORS.dim,
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <span>
          {progress < 100 ? (
            <>
              Installing:{" "}
              <span style={{ color: COLORS.text }}>{currentSkill}</span>
            </>
          ) : (
            <span style={{ color: COLORS.green }}>
              All skills installed successfully
            </span>
          )}
        </span>
        <span>
          {installedCount}/82 skills ({Math.round(progress)}%)
        </span>
      </div>

      {/* Skill list scrolling */}
      {progress < 100 && (
        <div
          style={{
            fontSize: 14,
            color: COLORS.dim,
            display: "flex",
            flexDirection: "column",
            gap: 4,
            marginLeft: 24,
            maxHeight: 100,
            overflow: "hidden",
          }}
        >
          {SKILL_NAMES.slice(
            Math.max(0, skillIndex - 2),
            skillIndex + 1
          ).map((skill, idx) => {
            const isActive = idx === Math.min(2, skillIndex);
            return (
              <div
                key={skill}
                style={{
                  color: isActive ? COLORS.text : COLORS.dim,
                  opacity: isActive ? 1 : 0.5,
                }}
              >
                {isActive ? "→" : " "} {skill}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
