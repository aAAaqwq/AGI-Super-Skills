import React from "react";
import {
  interpolate,
  useCurrentFrame,
  useVideoConfig,
  spring,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

// Apple-inspired color palette - clean, minimal, sophisticated
const COLORS = {
  white: "#ffffff",
  lightGray: "rgba(255, 255, 255, 0.7)",
  subtleGray: "rgba(255, 255, 255, 0.5)",
  accent: "rgba(255, 255, 255, 0.9)",
};

type StatItemProps = {
  value: string;
  label: string;
  delay: number;
  index: number;
};

const StatItem: React.FC<StatItemProps> = ({ value, label, delay, index }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const adjustedFrame = Math.max(0, frame - delay);

  // Faster spring for 2x speed
  const itemSpring = spring({
    frame: adjustedFrame,
    fps,
    config: { damping: 15, stiffness: 200, mass: 0.5 },
  });

  const opacity = interpolate(itemSpring, [0, 1], [0, 1]);
  const translateY = interpolate(itemSpring, [0, 1], [40, 0]);
  const scale = interpolate(itemSpring, [0, 1], [0.9, 1]);

  // Count-up animation for numbers - faster (2x speed)
  const countProgress = interpolate(
    adjustedFrame,
    [0, fps * 0.4],
    [0, 1],
    { extrapolateRight: "clamp" }
  );
  const targetValue = parseInt(value);
  const displayValue = Math.round(countProgress * targetValue);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 16,
        opacity,
        transform: `translateY(${translateY}px) scale(${scale})`,
      }}
    >
      {/* Large number */}
      <div
        style={{
          fontFamily,
          fontSize: 96,
          fontWeight: 600,
          color: COLORS.white,
          lineHeight: 1,
          letterSpacing: -4,
        }}
      >
        {displayValue}
      </div>
      {/* Label with refined typography */}
      <div
        style={{
          fontFamily,
          fontSize: 18,
          fontWeight: 500,
          color: COLORS.lightGray,
          textTransform: "uppercase",
          letterSpacing: 3,
        }}
      >
        {label}
      </div>
    </div>
  );
};

type StatsDisplayProps = {
  startDelay?: number;
};

export const StatsDisplay: React.FC<StatsDisplayProps> = ({
  startDelay = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const staggerDelay = 0.08 * fps; // Faster stagger (2x speed)

  const adjustedFrame = Math.max(0, frame - startDelay);

  // Overall container fade - faster
  const containerSpring = spring({
    frame: adjustedFrame,
    fps,
    config: { damping: 15, stiffness: 150 },
  });
  const containerOpacity = interpolate(containerSpring, [0, 1], [0, 1]);

  const stats = [
    { value: "82", label: "Skills" },
    { value: "20", label: "Categories" },
    { value: "5", label: "Agents" },
  ];

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 64,
        opacity: containerOpacity,
      }}
    >
      {/* Subtle tagline */}
      <div
        style={{
          fontFamily,
          fontSize: 24,
          fontWeight: 400,
          color: COLORS.subtleGray,
          letterSpacing: 1,
        }}
      >
        Everything you need for AI research
      </div>

      {/* Stats row with elegant spacing */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "flex-end",
          gap: 140,
        }}
      >
        {stats.map((stat, index) => (
          <StatItem
            key={stat.label}
            value={stat.value}
            label={stat.label}
            delay={startDelay + index * staggerDelay}
            index={index}
          />
        ))}
      </div>

      {/* Subtle divider line - faster animation */}
      <div
        style={{
          width: 60,
          height: 2,
          backgroundColor: COLORS.subtleGray,
          borderRadius: 1,
          opacity: interpolate(
            adjustedFrame,
            [fps * 0.3, fps * 0.5],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          ),
        }}
      />
    </div>
  );
};
