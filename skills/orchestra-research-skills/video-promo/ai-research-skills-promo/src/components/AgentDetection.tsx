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
  dim: "#8b949e",
  text: "#e6edf3",
};

const AGENTS = [
  { name: "Claude Code", path: "~/.claude/skills" },
  { name: "Cursor", path: "~/.cursor/skills" },
  { name: "Windsurf", path: "~/.codeium/windsurf/skills" },
  { name: "Gemini CLI", path: "~/.gemini/skills" },
  { name: "Kilo Code", path: "~/.kilocode/skills" },
];

type AgentItemProps = {
  name: string;
  path: string;
  delay: number;
};

const AgentItem: React.FC<AgentItemProps> = ({ name, path, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const adjustedFrame = Math.max(0, frame - delay);

  const itemSpring = spring({
    frame: adjustedFrame,
    fps,
    config: { damping: 20, stiffness: 200 },
  });

  const opacity = interpolate(itemSpring, [0, 1], [0, 1]);
  const translateX = interpolate(itemSpring, [0, 1], [-20, 0]);

  // Checkmark animation
  const checkDelay = 8;
  const checkSpring = spring({
    frame: adjustedFrame - checkDelay,
    fps,
    config: { damping: 10, stiffness: 200 },
  });

  const checkScale = interpolate(checkSpring, [0, 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        opacity,
        transform: `translateX(${translateX}px)`,
        fontFamily: monoFont,
        fontSize: 20,
      }}
    >
      <span
        style={{
          color: COLORS.green,
          transform: `scale(${checkScale})`,
          display: "inline-block",
          width: 24,
        }}
      >
        {checkScale > 0.5 ? "●" : "○"}
      </span>
      <span style={{ color: COLORS.text, width: 160 }}>{name}</span>
      <span style={{ color: COLORS.dim }}>{path}</span>
    </div>
  );
};

type AgentDetectionProps = {
  startDelay?: number;
};

export const AgentDetection: React.FC<AgentDetectionProps> = ({
  startDelay = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const staggerDelay = 0.2 * fps;

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
        gap: 24,
      }}
    >
      <div
        style={{
          fontFamily: monoFont,
          fontSize: 18,
          color: COLORS.green,
          opacity: headerOpacity,
        }}
      >
        ✓ Found 5 coding agents
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 12,
          marginLeft: 24,
        }}
      >
        {AGENTS.map((agent, index) => (
          <AgentItem
            key={agent.name}
            name={agent.name}
            path={agent.path}
            delay={startDelay + 0.3 * fps + index * staggerDelay}
          />
        ))}
      </div>
    </div>
  );
};
