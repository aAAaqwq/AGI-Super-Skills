import React from "react";
import {
  interpolate,
  useCurrentFrame,
  useVideoConfig,
  spring,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/JetBrainsMono";

const { fontFamily: monoFont } = loadFont();

const COLORS = {
  green: "#3fb950",
  cyan: "#58a6ff",
  yellow: "#d29922",
  dim: "#8b949e",
  text: "#e6edf3",
  selected: "#238636",
};

const CATEGORIES = [
  { name: "Post-Training", skills: 8, examples: "GRPO, verl, slime, miles" },
  { name: "Fine-Tuning", skills: 5, examples: "Axolotl, Unsloth, PEFT" },
  { name: "Inference Serving", skills: 4, examples: "vLLM, SGLang, TensorRT" },
  { name: "Distributed Training", skills: 6, examples: "DeepSpeed, FSDP" },
  { name: "Optimization", skills: 6, examples: "Flash Attention, GPTQ, AWQ" },
  { name: "Evaluation", skills: 3, examples: "lm-eval-harness, Inspect AI" },
];

type CategoryItemProps = {
  name: string;
  skills: number;
  delay: number;
  selected?: boolean;
  showCheck?: boolean;
};

const CategoryItem: React.FC<CategoryItemProps> = ({
  name,
  skills,
  delay,
  selected = false,
  showCheck = false,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const adjustedFrame = Math.max(0, frame - delay);

  const itemSpring = spring({
    frame: adjustedFrame,
    fps,
    config: { damping: 20, stiffness: 150 },
  });

  const opacity = interpolate(itemSpring, [0, 1], [0, 1]);
  const translateY = interpolate(itemSpring, [0, 1], [15, 0]);

  // Selection animation happens later
  const selectDelay = 0.8 * fps;
  const selectSpring = spring({
    frame: adjustedFrame - selectDelay,
    fps,
    config: { damping: 15, stiffness: 200 },
  });

  const checkOpacity = showCheck
    ? interpolate(selectSpring, [0, 1], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 0;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        opacity,
        transform: `translateY(${translateY}px)`,
        fontFamily: monoFont,
        fontSize: 18,
        padding: "8px 0",
      }}
    >
      <span
        style={{
          width: 24,
          color: showCheck ? COLORS.green : COLORS.dim,
          opacity: showCheck ? checkOpacity : opacity,
        }}
      >
        {showCheck && checkOpacity > 0.5 ? "◉" : "○"}
      </span>
      <span
        style={{
          color: COLORS.text,
          width: 200,
        }}
      >
        {name}
      </span>
      <span
        style={{
          color: COLORS.dim,
        }}
      >
        {skills} skills
      </span>
    </div>
  );
};

type CategorySelectionProps = {
  startDelay?: number;
};

export const CategorySelection: React.FC<CategorySelectionProps> = ({
  startDelay = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const staggerDelay = 0.1 * fps;

  // Header animation
  const headerSpring = spring({
    frame: Math.max(0, frame - startDelay),
    fps,
    config: { damping: 200 },
  });

  const headerOpacity = interpolate(headerSpring, [0, 1], [0, 1]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div
        style={{
          fontFamily: monoFont,
          fontSize: 16,
          color: COLORS.dim,
          opacity: headerOpacity,
          marginBottom: 8,
        }}
      >
        What would you like to install?
      </div>

      <div
        style={{
          fontFamily: monoFont,
          fontSize: 20,
          color: COLORS.cyan,
          opacity: headerOpacity,
          marginBottom: 16,
        }}
      >
        {">"} Everything (82 skills)
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          marginLeft: 8,
        }}
      >
        {CATEGORIES.map((cat, index) => (
          <CategoryItem
            key={cat.name}
            name={cat.name}
            skills={cat.skills}
            delay={startDelay + 0.3 * fps + index * staggerDelay}
            showCheck={true}
          />
        ))}
      </div>
    </div>
  );
};
