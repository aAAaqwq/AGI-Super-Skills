import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate, Img, staticFile } from 'remotion';
import { colors } from '../styles/colors';

const FPS = 30;

export const ClosingLogo = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Timeline (1.5x speed):
  // 0-0.3s: Fade to black
  // 0.3-1.3s: Logo bounces in
  // 1-1.7s: Tagline fades in
  // 1.7-3s: GitHub URL fades in

  // Logo entrance (1.5x speed)
  const logoEntrance = spring({
    frame: frame - 0.3 * fps,
    fps,
    config: { damping: 12, stiffness: 120 },
  });

  const logoScale = interpolate(logoEntrance, [0, 1], [0.5, 1]);
  const logoOpacity = interpolate(logoEntrance, [0, 1], [0, 1], {
    extrapolateRight: 'clamp',
  });

  // Glow pulse animation (stronger, more visible)
  const glowCycle = (frame - 0.8 * fps) / fps;
  const glowIntensity = logoEntrance > 0.5
    ? 40 + 80 * Math.sin(glowCycle * Math.PI * 2)
    : 40;

  // Tagline with spring entrance
  const taglineEntrance = spring({
    frame: frame - 1 * fps,
    fps,
    config: { damping: 15, stiffness: 120 },
  });
  const taglineOpacity = interpolate(taglineEntrance, [0, 1], [0, 1], {
    extrapolateRight: 'clamp',
  });
  const taglineTranslateY = interpolate(taglineEntrance, [0, 1], [20, 0], {
    extrapolateRight: 'clamp',
  });

  // GitHub URL with spring entrance
  const urlEntrance = spring({
    frame: frame - 1.7 * fps,
    fps,
    config: { damping: 18, stiffness: 100 },
  });
  const urlOpacity = interpolate(urlEntrance, [0, 1], [0, 1], {
    extrapolateRight: 'clamp',
  });
  const urlTranslateY = interpolate(urlEntrance, [0, 1], [15, 0], {
    extrapolateRight: 'clamp',
  });

  // Background particles (floating stars)
  const particles = [
    { x: 200, y: 150, size: 3, speed: 0.02, phase: 0 },
    { x: 1700, y: 200, size: 2, speed: 0.025, phase: 1.2 },
    { x: 350, y: 800, size: 2.5, speed: 0.018, phase: 2.4 },
    { x: 1550, y: 750, size: 3, speed: 0.022, phase: 0.8 },
    { x: 960, y: 100, size: 2, speed: 0.03, phase: 1.8 },
    { x: 600, y: 300, size: 2, speed: 0.015, phase: 3.2 },
    { x: 1400, y: 450, size: 2.5, speed: 0.02, phase: 2.0 },
    { x: 300, y: 500, size: 2, speed: 0.028, phase: 0.5 },
  ];

  const getParticleStyle = (particle: typeof particles[0]) => {
    const floatPhase = frame * particle.speed + particle.phase;
    const floatY = Math.sin(floatPhase) * 15;
    const floatX = Math.cos(floatPhase * 0.7) * 8;
    const twinkle = 0.3 + 0.7 * ((Math.sin(floatPhase * 2) + 1) / 2);

    return {
      position: 'absolute' as const,
      left: particle.x + floatX,
      top: particle.y + floatY,
      width: particle.size,
      height: particle.size,
      borderRadius: '50%',
      backgroundColor: colors.primary,
      opacity: twinkle * logoOpacity,
      boxShadow: `0 0 ${particle.size * 3}px ${colors.primary}60`,
    };
  };

  return (
    <AbsoluteFill
      style={{
        backgroundColor: colors.bgDark,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '32px',
      }}
    >
      {/* Background floating particles */}
      {particles.map((particle, i) => (
        <div key={i} style={getParticleStyle(particle)} />
      ))}

      {/* Logo */}
      <div
        style={{
          transform: `scale(${logoScale})`,
          opacity: logoOpacity,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '24px',
        }}
      >
        {/* Actual logo image */}
        <Img
          src={staticFile('logo.png')}
          style={{
            width: 420,
            height: 'auto',
            filter: `drop-shadow(0 0 ${glowIntensity}px ${colors.primary}80)`,
          }}
        />
      </div>

      {/* Tagline */}
      <p
        style={{
          fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
          fontSize: '36px',
          fontWeight: 500,
          color: colors.textPrimary,
          margin: 0,
          opacity: taglineOpacity,
          transform: `translateY(${taglineTranslateY}px)`,
          textShadow: '0 2px 10px rgba(0,0,0,0.3)',
        }}
      >
        Edit once, sync everywhere.
      </p>

      {/* GitHub URL */}
      <p
        style={{
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: '20px',
          color: colors.primary,
          margin: 0,
          marginTop: '24px',
          opacity: urlOpacity,
          transform: `translateY(${urlTranslateY}px)`,
          textShadow: `0 0 ${10 + 5 * Math.sin(frame * 0.1)}px ${colors.primary}40`,
        }}
      >
        github.com/runkids/skillshare
      </p>
    </AbsoluteFill>
  );
};
