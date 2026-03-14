import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/JetBrainsMono";

const { fontFamily: monoFont } = loadFont();

// Terminal color scheme (dark theme)
const COLORS = {
  bg: "#1a1a2e",
  terminalBg: "#0d1117",
  terminalBorder: "#30363d",
  text: "#e6edf3",
  green: "#3fb950",
  cyan: "#58a6ff",
  yellow: "#d29922",
  red: "#f85149",
  dim: "#8b949e",
  purple: "#a371f7",
};

type TerminalProps = {
  children: React.ReactNode;
  title?: string;
  showControls?: boolean;
};

export const Terminal: React.FC<TerminalProps> = ({
  children,
  title = "zsh",
  showControls = true,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Fade in the terminal
  const opacity = interpolate(frame, [0, 0.5 * fps], [0, 1], {
    extrapolateRight: "clamp",
  });

  const scale = interpolate(frame, [0, 0.5 * fps], [0.95, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        opacity,
        transform: `scale(${scale})`,
        width: "85%",
        maxWidth: 1400,
        borderRadius: 12,
        overflow: "hidden",
        boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
        border: `1px solid ${COLORS.terminalBorder}`,
      }}
    >
      {/* Terminal Header */}
      <div
        style={{
          backgroundColor: "#161b22",
          padding: "12px 16px",
          display: "flex",
          alignItems: "center",
          gap: 8,
          borderBottom: `1px solid ${COLORS.terminalBorder}`,
        }}
      >
        {showControls && (
          <div style={{ display: "flex", gap: 8 }}>
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: "50%",
                backgroundColor: "#f85149",
              }}
            />
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: "50%",
                backgroundColor: "#d29922",
              }}
            />
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: "50%",
                backgroundColor: "#3fb950",
              }}
            />
          </div>
        )}
        <div
          style={{
            flex: 1,
            textAlign: "center",
            color: COLORS.dim,
            fontFamily: monoFont,
            fontSize: 14,
          }}
        >
          {title}
        </div>
        <div style={{ width: 52 }} /> {/* Spacer for centering */}
      </div>

      {/* Terminal Body */}
      <div
        style={{
          backgroundColor: COLORS.terminalBg,
          padding: "24px 32px",
          minHeight: 400,
          fontFamily: monoFont,
          fontSize: 18,
          lineHeight: 1.6,
          color: COLORS.text,
        }}
      >
        {children}
      </div>
    </div>
  );
};

// Typing cursor component
type CursorProps = {
  visible?: boolean;
};

export const Cursor: React.FC<CursorProps> = ({ visible = true }) => {
  const frame = useCurrentFrame();
  const blinkFrames = 15;

  const opacity = visible
    ? interpolate(
        frame % blinkFrames,
        [0, blinkFrames / 2, blinkFrames],
        [1, 0, 1],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
      )
    : 0;

  return (
    <span
      style={{
        opacity,
        backgroundColor: COLORS.green,
        width: 10,
        height: 22,
        display: "inline-block",
        marginLeft: 2,
        verticalAlign: "middle",
      }}
    />
  );
};

// Typewriter text component
type TypewriterProps = {
  text: string;
  startFrame?: number;
  charsPerFrame?: number;
  color?: string;
  showCursor?: boolean;
};

export const Typewriter: React.FC<TypewriterProps> = ({
  text,
  startFrame = 0,
  charsPerFrame = 0.5,
  color = COLORS.text,
  showCursor = true,
}) => {
  const frame = useCurrentFrame();

  const adjustedFrame = Math.max(0, frame - startFrame);
  const typedChars = Math.min(
    text.length,
    Math.floor(adjustedFrame * charsPerFrame)
  );
  const displayedText = text.slice(0, typedChars);
  const isComplete = typedChars >= text.length;

  return (
    <span style={{ color }}>
      {displayedText}
      {showCursor && !isComplete && <Cursor />}
    </span>
  );
};

// Command line with prompt
type CommandLineProps = {
  command: string;
  startFrame?: number;
  prompt?: string;
};

export const CommandLine: React.FC<CommandLineProps> = ({
  command,
  startFrame = 0,
  prompt = "$ ",
}) => {
  return (
    <div style={{ display: "flex" }}>
      <span style={{ color: COLORS.green }}>{prompt}</span>
      <Typewriter text={command} startFrame={startFrame} charsPerFrame={0.8} />
    </div>
  );
};

// Colored text span
type ColoredTextProps = {
  children: React.ReactNode;
  color: keyof typeof COLORS;
};

export const ColoredText: React.FC<ColoredTextProps> = ({ children, color }) => {
  return <span style={{ color: COLORS[color] }}>{children}</span>;
};

export { COLORS };
