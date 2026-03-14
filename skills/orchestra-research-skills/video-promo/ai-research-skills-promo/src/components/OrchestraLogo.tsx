import React from "react";
import {
  interpolate,
  useCurrentFrame,
  useVideoConfig,
  spring,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/JetBrainsMono";

const { fontFamily: monoFont } = loadFont();

// ASCII ORCHESTRA logo from the package
const ORCHESTRA_ASCII = `
 ██████╗ ██████╗  ██████╗ ██╗  ██╗ ███████╗ ███████╗ ████████╗ ██████╗   █████╗
██╔═══██╗██╔══██╗██╔════╝ ██║  ██║ ██╔════╝ ██╔════╝ ╚══██╔══╝ ██╔══██╗ ██╔══██╗
██║   ██║██████╔╝██║      ███████║ █████╗   ███████╗    ██║    ██████╔╝ ███████║
██║   ██║██╔══██╗██║      ██╔══██║ ██╔══╝   ╚════██║    ██║    ██╔══██╗ ██╔══██║
╚██████╔╝██║  ██║╚██████╗ ██║  ██║ ███████╗ ███████║    ██║    ██║  ██║ ██║  ██║
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ╚══════╝ ╚══════╝    ╚═╝    ╚═╝  ╚═╝ ╚═╝  ╚═╝
`;

type OrchestraLogoProps = {
  showSubtitle?: boolean;
  animationDelay?: number;
};

export const OrchestraLogo: React.FC<OrchestraLogoProps> = ({
  showSubtitle = true,
  animationDelay = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const adjustedFrame = Math.max(0, frame - animationDelay);

  // Logo fade in with spring
  const logoSpring = spring({
    frame: adjustedFrame,
    fps,
    config: { damping: 200 },
  });

  const logoOpacity = interpolate(logoSpring, [0, 1], [0, 1]);
  const logoScale = interpolate(logoSpring, [0, 1], [0.8, 1]);

  // Subtitle appears after logo
  const subtitleDelay = 0.5 * fps;
  const subtitleSpring = spring({
    frame: adjustedFrame - subtitleDelay,
    fps,
    config: { damping: 200 },
  });

  const subtitleOpacity = interpolate(subtitleSpring, [0, 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <pre
        style={{
          fontFamily: monoFont,
          fontSize: 14,
          lineHeight: 1.1,
          color: "#ffffff",
          opacity: logoOpacity,
          transform: `scale(${logoScale})`,
          textAlign: "center",
          margin: 0,
          letterSpacing: -1,
        }}
      >
        {ORCHESTRA_ASCII}
      </pre>

      {showSubtitle && (
        <div
          style={{
            marginTop: 24,
            opacity: subtitleOpacity,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 16,
          }}
        >
          <div
            style={{
              fontFamily: "system-ui, -apple-system, sans-serif",
              fontSize: 32,
              fontWeight: 600,
              color: "#ffffff",
              letterSpacing: 2,
            }}
          >
            AI Research Skills
          </div>
          <div
            style={{
              fontFamily: monoFont,
              fontSize: 18,
              color: "#8b949e",
            }}
          >
            Expert-level knowledge for AI research engineering
          </div>
        </div>
      )}
    </div>
  );
};
