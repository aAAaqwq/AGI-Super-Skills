import { useCurrentFrame, useVideoConfig } from 'remotion';
import { Cursor } from './Cursor';
import { colors } from '../styles/colors';

type TypewriterProps = {
  text: string;
  startFrame?: number;
  speed?: number; // frames per character
  showCursor?: boolean;
  prefix?: string;
  color?: string;
  style?: React.CSSProperties;
  showPrompt?: boolean;
};

export const Typewriter = ({
  text,
  startFrame = 0,
  speed = 2, // 2 frames per character (~66ms at 30fps)
  showCursor = true,
  prefix = '$ ',
  color = colors.terminalText,
  style,
  showPrompt = true,
}: TypewriterProps) => {
  const frame = useCurrentFrame();

  const elapsed = Math.max(0, frame - startFrame);
  const charsToShow = Math.floor(elapsed / speed);
  const visibleText = text.slice(0, charsToShow);
  const isTyping = charsToShow < text.length && elapsed > 0;
  const isDone = charsToShow >= text.length;

  const finalColor = style?.color || color;

  return (
    <div
      style={{
        fontFamily: '"JetBrains Mono", "SF Mono", monospace',
        fontSize: '24px',
        color: finalColor,
        whiteSpace: 'pre',
        ...style,
      }}
    >
      {showPrompt && <span style={{ color: colors.terminalGreen }}>{prefix}</span>}
      {visibleText}
      {showCursor && (isTyping || isDone) && <Cursor color={finalColor} />}
    </div>
  );
};
