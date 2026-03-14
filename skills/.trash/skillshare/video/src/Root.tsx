import { Composition, Folder } from 'remotion';
import { PromoVideo } from './PromoVideo';
import { PainPoint } from './scenes/PainPoint';
import { TerminalDemo } from './scenes/TerminalDemo';
import { Architecture } from './scenes/Architecture';
import { OrganizationFeature } from './scenes/OrganizationFeature';
import { AIFeature } from './scenes/AIFeature';
import { ClosingLogo } from './scenes/ClosingLogo';

// Video specs
const FPS = 30;
const WIDTH = 1920;
const HEIGHT = 1080;

export const RemotionRoot = () => {
  return (
    <>
      {/* Main promo video - 22.3 seconds */}
      <Composition
        id="PromoVideo"
        component={PromoVideo}
        durationInFrames={22.3 * FPS}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
      />

      {/* Individual scenes for preview/testing */}
      <Folder name="Scenes">
        <Composition
          id="Scene1-PainPoint"
          component={PainPoint}
          durationInFrames={3.3 * FPS}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
        <Composition
          id="Scene2-TerminalDemo"
          component={TerminalDemo}
          durationInFrames={5.3 * FPS}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
        <Composition
          id="Scene3-Architecture"
          component={Architecture}
          durationInFrames={2.7 * FPS}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
        <Composition
          id="Scene4-Organization"
          component={OrganizationFeature}
          durationInFrames={4 * FPS}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
        <Composition
          id="Scene5-AIFeature"
          component={AIFeature}
          durationInFrames={4 * FPS}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
        <Composition
          id="Scene6-ClosingLogo"
          component={ClosingLogo}
          durationInFrames={3 * FPS}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
      </Folder>
    </>
  );
};
