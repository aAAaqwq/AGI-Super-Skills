import { useCurrentFrame, useVideoConfig, interpolate } from 'remotion';
import { colors } from '../styles/colors';

type CursorProps = {
  blinkInterval?: number; // in frames
  color?: string;
};

export const Cursor = ({ blinkInterval = 15, color = colors.terminalText }: CursorProps) => {
  const frame = useCurrentFrame();

  // Create blinking effect using modulo
  const cyclePosition = frame % (blinkInterval * 2);
  const opacity = cyclePosition < blinkInterval ? 1 : 0;

  return (
    <span
      style={{
        display: 'inline-block',
        width: '10px',
        height: '22px',
        backgroundColor: color,
        opacity,
        verticalAlign: 'middle',
        marginLeft: '2px',
      }}
    />
  );
};
