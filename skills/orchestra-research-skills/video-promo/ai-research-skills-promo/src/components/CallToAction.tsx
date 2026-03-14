import React from "react";
import {
  interpolate,
  useCurrentFrame,
  useVideoConfig,
  spring,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/JetBrainsMono";
import { loadFont as loadInterFont } from "@remotion/google-fonts/Inter";

const { fontFamily: monoFont } = loadFont();
const { fontFamily: interFont } = loadInterFont();

const COLORS = {
  green: "#3fb950",
  cyan: "#58a6ff",
  yellow: "#d29922",
  dim: "#8b949e",
  text: "#e6edf3",
  bg: "#0d1117",
};

type CallToActionProps = {
  startDelay?: number;
};

export const CallToAction: React.FC<CallToActionProps> = ({
  startDelay = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const adjustedFrame = Math.max(0, frame - startDelay);

  // Main animation
  const mainSpring = spring({
    frame: adjustedFrame,
    fps,
    config: { damping: 15, stiffness: 100 },
  });

  const opacity = interpolate(mainSpring, [0, 1], [0, 1]);
  const scale = interpolate(mainSpring, [0, 1], [0.9, 1]);

  // Command animation
  const cmdDelay = 0.5 * fps;
  const cmdSpring = spring({
    frame: adjustedFrame - cmdDelay,
    fps,
    config: { damping: 200 },
  });

  const cmdOpacity = interpolate(cmdSpring, [0, 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Blinking cursor
  const cursorBlink = interpolate(
    adjustedFrame % 30,
    [0, 15, 30],
    [1, 0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // URL animation
  const urlDelay = 1 * fps;
  const urlSpring = spring({
    frame: adjustedFrame - urlDelay,
    fps,
    config: { damping: 200 },
  });

  const urlOpacity = interpolate(urlSpring, [0, 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 48,
        opacity,
        transform: `scale(${scale})`,
      }}
    >
      {/* Main heading */}
      <div
        style={{
          fontFamily: interFont,
          fontSize: 56,
          fontWeight: 700,
          color: COLORS.text,
          textAlign: "center",
          lineHeight: 1.2,
        }}
      >
        Get Started in{" "}
        <span style={{ color: COLORS.cyan }}>One Command</span>
      </div>

      {/* Command box */}
      <div
        style={{
          backgroundColor: COLORS.bg,
          borderRadius: 12,
          padding: "24px 48px",
          opacity: cmdOpacity,
          boxShadow: "0 0 40px rgba(88, 166, 255, 0.15)",
          border: "1px solid #30363d",
        }}
      >
        <div
          style={{
            fontFamily: monoFont,
            fontSize: 28,
            color: COLORS.dim,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <span style={{ color: COLORS.green }}>$</span>
          <span style={{ color: COLORS.text }}>
            npx @orchestra-research/ai-research-skills
          </span>
          <span
            style={{
              width: 14,
              height: 28,
              backgroundColor: COLORS.green,
              opacity: cursorBlink,
              marginLeft: 2,
            }}
          />
        </div>
      </div>

      {/* GitHub URL */}
      <div
        style={{
          fontFamily: monoFont,
          fontSize: 18,
          color: COLORS.dim,
          opacity: urlOpacity,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 12,
        }}
      >
        <span>github.com/orchestra-research/ai-research-skills</span>
        <div
          style={{
            display: "flex",
            gap: 24,
            marginTop: 8,
          }}
        >
          <span style={{ color: COLORS.yellow }}>★ Star on GitHub</span>
          <span style={{ color: COLORS.cyan }}>npm i @orchestra-research/ai-research-skills</span>
        </div>
      </div>
    </div>
  );
};
