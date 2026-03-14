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

// Apple-inspired color palette
const COLORS = {
  white: "#ffffff",
  lightGray: "rgba(255, 255, 255, 0.7)",
  subtleGray: "rgba(255, 255, 255, 0.5)",
  dimGray: "rgba(255, 255, 255, 0.4)",
  accent: "rgba(255, 255, 255, 0.9)",
};

const EXAMPLE_PROMPTS = [
  "Help me set up GRPO training with verl",
  "How do I serve a model with vLLM?",
  "Write a NeurIPS paper introduction",
];

type SuccessScreenProps = {
  startDelay?: number;
};

export const SuccessScreen: React.FC<SuccessScreenProps> = ({
  startDelay = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const adjustedFrame = Math.max(0, frame - startDelay);

  // Main title animation - smooth and elegant
  const titleSpring = spring({
    frame: adjustedFrame,
    fps,
    config: { damping: 22, stiffness: 70, mass: 1 },
  });

  const titleOpacity = interpolate(titleSpring, [0, 1], [0, 1]);
  const titleScale = interpolate(titleSpring, [0, 1], [0.95, 1]);

  // Subtitle animation
  const subtitleDelay = 0.4 * fps;
  const subtitleSpring = spring({
    frame: adjustedFrame - subtitleDelay,
    fps,
    config: { damping: 25, stiffness: 60 },
  });

  const subtitleOpacity = interpolate(subtitleSpring, [0, 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Examples animation
  const examplesDelay = 0.8 * fps;
  const staggerDelay = 0.15 * fps;

  // Checkmark animation - elegant circle reveal
  const checkDelay = 0.1 * fps;
  const checkSpring = spring({
    frame: adjustedFrame - checkDelay,
    fps,
    config: { damping: 18, stiffness: 100 },
  });
  const checkScale = interpolate(checkSpring, [0, 1], [0, 1]);
  const checkOpacity = interpolate(checkSpring, [0, 1], [0, 1]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 48,
        textAlign: "center",
      }}
    >
      {/* Elegant checkmark circle */}
      <div
        style={{
          width: 80,
          height: 80,
          borderRadius: "50%",
          border: "2px solid rgba(255, 255, 255, 0.3)",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          opacity: checkOpacity,
          transform: `scale(${checkScale})`,
        }}
      >
        <svg
          width="36"
          height="36"
          viewBox="0 0 24 24"
          fill="none"
          stroke={COLORS.white}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </div>

      {/* Success title - clean typography */}
      <div
        style={{
          opacity: titleOpacity,
          transform: `scale(${titleScale})`,
        }}
      >
        <div
          style={{
            fontFamily: interFont,
            fontSize: 52,
            fontWeight: 600,
            color: COLORS.white,
            marginBottom: 16,
            letterSpacing: -1,
          }}
        >
          Ready to go
        </div>
        <div
          style={{
            fontFamily: interFont,
            fontSize: 22,
            fontWeight: 400,
            color: COLORS.lightGray,
          }}
        >
          <span style={{ color: COLORS.white, fontWeight: 500 }}>82</span> skills
          installed across{" "}
          <span style={{ color: COLORS.white, fontWeight: 500 }}>5</span> agents
        </div>
      </div>

      {/* Divider */}
      <div
        style={{
          width: 40,
          height: 1,
          backgroundColor: COLORS.subtleGray,
          opacity: subtitleOpacity,
        }}
      />

      {/* Example prompts section */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 20,
          alignItems: "center",
          opacity: subtitleOpacity,
        }}
      >
        <div
          style={{
            fontFamily: interFont,
            fontSize: 16,
            fontWeight: 500,
            color: COLORS.dimGray,
            textTransform: "uppercase",
            letterSpacing: 2,
          }}
        >
          Try asking
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 14,
            alignItems: "center",
          }}
        >
          {EXAMPLE_PROMPTS.map((prompt, index) => {
            const promptSpring = spring({
              frame: adjustedFrame - examplesDelay - index * staggerDelay,
              fps,
              config: { damping: 22, stiffness: 100 },
            });

            const promptOpacity = interpolate(promptSpring, [0, 1], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });

            const promptTranslateY = interpolate(promptSpring, [0, 1], [15, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });

            return (
              <div
                key={prompt}
                style={{
                  fontFamily: monoFont,
                  fontSize: 17,
                  color: COLORS.lightGray,
                  opacity: promptOpacity,
                  transform: `translateY(${promptTranslateY}px)`,
                  padding: "12px 24px",
                  backgroundColor: "rgba(255, 255, 255, 0.05)",
                  borderRadius: 8,
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                }}
              >
                "{prompt}"
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
