import { AbsoluteFill, Sequence } from 'remotion';
import { PainPoint } from './scenes/PainPoint';
import { TerminalDemo } from './scenes/TerminalDemo';
import { Architecture } from './scenes/Architecture';
import { OrganizationFeature } from './scenes/OrganizationFeature';
import { AIFeature } from './scenes/AIFeature';
import { ClosingLogo } from './scenes/ClosingLogo';
import { SceneWrapper } from './components/Transition3D';
import { colors } from './styles/colors';

const FPS = 30;

// 1.5x speed: 28s -> ~19s
export const PromoVideo = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: colors.bgDark }}>
      {/* Scene 1: Pain Point (0-3.3s) */}
      <Sequence from={0} durationInFrames={3.3 * FPS}>
        <SceneWrapper entranceType="zoomRotate" exitType="flipOut">
          <PainPoint />
        </SceneWrapper>
      </Sequence>

      {/* Scene 2: Terminal Demo (3.3-8.6s) */}
      <Sequence from={3.3 * FPS} durationInFrames={5.3 * FPS}>
        <SceneWrapper entranceType="slideUp" exitType="flipOut">
          <TerminalDemo />
        </SceneWrapper>
      </Sequence>

      {/* Scene 3: Architecture Diagram (8.6-11.3s) - shortened by 2s */}
      <Sequence from={8.6 * FPS} durationInFrames={2.7 * FPS}>
        <SceneWrapper entranceType="flipIn" exitType="flipOut">
          <Architecture />
        </SceneWrapper>
      </Sequence>

      {/* Scene 4: Organization Feature (11.3-15.3s) */}
      <Sequence from={11.3 * FPS} durationInFrames={4 * FPS}>
        <SceneWrapper entranceType="slideUp" exitType="flipOut">
          <OrganizationFeature />
        </SceneWrapper>
      </Sequence>

      {/* Scene 5: AI Feature (15.3-19.3s) */}
      <Sequence from={15.3 * FPS} durationInFrames={4 * FPS}>
        <SceneWrapper entranceType="slideUp" exitType="fadeOut">
          <AIFeature />
        </SceneWrapper>
      </Sequence>

      {/* Scene 6: Closing Logo (19.3-22.3s) */}
      <Sequence from={19.3 * FPS} durationInFrames={3 * FPS}>
        <SceneWrapper entranceType="zoomRotate" exitType="none">
          <ClosingLogo />
        </SceneWrapper>
      </Sequence>
    </AbsoluteFill>
  );
};
