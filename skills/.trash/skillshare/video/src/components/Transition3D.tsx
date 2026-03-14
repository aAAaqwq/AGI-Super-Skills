import { ReactNode } from 'react';
import { useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';

type Transition3DProps = {
  children: ReactNode;
  type?: 'slideUp' | 'flipIn' | 'flipOut' | 'zoomRotate';
  delay?: number;
  duration?: number;
};

export const Transition3D = ({
  children,
  type = 'slideUp',
  delay = 0,
  duration,
}: Transition3DProps) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const effectiveDuration = duration ?? durationInFrames;

  // Slide up entrance with 3D rotation
  if (type === 'slideUp') {
    const entrance = spring({
      frame: frame - delay,
      fps,
      config: { damping: 200, stiffness: 100 },
    });

    const translateY = interpolate(entrance, [0, 1], [400, 0]);
    const rotateX = interpolate(entrance, [0, 1], [30, 0]);
    const scale = interpolate(entrance, [0, 1], [0.8, 1]);
    const opacity = interpolate(entrance, [0, 1], [0, 1], {
      extrapolateRight: 'clamp',
    });

    return (
      <div
        style={{
          width: '100%',
          height: '100%',
          perspective: 1000,
        }}
      >
        <div
          style={{
            width: '100%',
            height: '100%',
            transform: `translateY(${translateY}px) rotateX(${rotateX}deg) scale(${scale})`,
            opacity,
            transformOrigin: 'center bottom',
          }}
        >
          {children}
        </div>
      </div>
    );
  }

  // Flip in from top
  if (type === 'flipIn') {
    const entrance = spring({
      frame: frame - delay,
      fps,
      config: { damping: 15, stiffness: 80 },
    });

    const rotateX = interpolate(entrance, [0, 1], [-90, 0]);
    const opacity = interpolate(entrance, [0, 1], [0, 1], {
      extrapolateRight: 'clamp',
    });

    return (
      <div
        style={{
          width: '100%',
          height: '100%',
          perspective: 1200,
        }}
      >
        <div
          style={{
            width: '100%',
            height: '100%',
            transform: `rotateX(${rotateX}deg)`,
            opacity,
            transformOrigin: 'center top',
          }}
        >
          {children}
        </div>
      </div>
    );
  }

  // Flip out to bottom
  if (type === 'flipOut') {
    const exitStart = effectiveDuration - 0.5 * fps;
    const exitProgress = interpolate(frame, [exitStart, effectiveDuration], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });

    const rotateX = interpolate(exitProgress, [0, 1], [0, 90]);
    const opacity = interpolate(exitProgress, [0, 1], [1, 0]);

    return (
      <div
        style={{
          width: '100%',
          height: '100%',
          perspective: 1200,
        }}
      >
        <div
          style={{
            width: '100%',
            height: '100%',
            transform: `rotateX(${rotateX}deg)`,
            opacity,
            transformOrigin: 'center bottom',
          }}
        >
          {children}
        </div>
      </div>
    );
  }

  // Zoom with subtle rotation throughout
  if (type === 'zoomRotate') {
    const entrance = spring({
      frame: frame - delay,
      fps,
      config: { damping: 200, stiffness: 100 },
    });

    // Continuous subtle Y rotation
    const rotateY = interpolate(frame, [0, effectiveDuration], [8, -8]);
    const scale = interpolate(entrance, [0, 1], [0.9, 1]);
    const opacity = interpolate(entrance, [0, 1], [0, 1], {
      extrapolateRight: 'clamp',
    });

    return (
      <div
        style={{
          width: '100%',
          height: '100%',
          perspective: 1000,
        }}
      >
        <div
          style={{
            width: '100%',
            height: '100%',
            transform: `scale(${scale}) rotateY(${rotateY}deg)`,
            opacity,
            transformOrigin: 'center center',
          }}
        >
          {children}
        </div>
      </div>
    );
  }

  return <>{children}</>;
};

// Scene wrapper with entrance and exit transitions
type SceneWrapperProps = {
  children: ReactNode;
  entranceType?: 'slideUp' | 'flipIn' | 'zoomRotate';
  exitType?: 'flipOut' | 'fadeOut' | 'none';
  entranceDelay?: number;
};

export const SceneWrapper = ({
  children,
  entranceType = 'slideUp',
  exitType = 'flipOut',
  entranceDelay = 0,
}: SceneWrapperProps) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Entrance animation
  const entrance = spring({
    frame: frame - entranceDelay,
    fps,
    config: { damping: 200, stiffness: 100 },
  });

  // Exit animation (last 0.4s)
  const exitStart = durationInFrames - 0.4 * fps;
  const exitProgress = interpolate(frame, [exitStart, durationInFrames], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // Entrance transforms
  let entranceTransform = '';
  let entranceOpacity = 1;

  if (entranceType === 'slideUp') {
    const translateY = interpolate(entrance, [0, 1], [300, 0]);
    const rotateX = interpolate(entrance, [0, 1], [20, 0]);
    const scale = interpolate(entrance, [0, 1], [0.85, 1]);
    entranceTransform = `translateY(${translateY}px) rotateX(${rotateX}deg) scale(${scale})`;
    entranceOpacity = interpolate(entrance, [0, 1], [0, 1], { extrapolateRight: 'clamp' });
  } else if (entranceType === 'flipIn') {
    const rotateX = interpolate(entrance, [0, 1], [-60, 0]);
    entranceTransform = `rotateX(${rotateX}deg)`;
    entranceOpacity = interpolate(entrance, [0, 1], [0, 1], { extrapolateRight: 'clamp' });
  } else if (entranceType === 'zoomRotate') {
    const scale = interpolate(entrance, [0, 1], [0.9, 1]);
    const rotateY = interpolate(entrance, [0, 1], [15, 0]);
    entranceTransform = `scale(${scale}) rotateY(${rotateY}deg)`;
    entranceOpacity = interpolate(entrance, [0, 1], [0, 1], { extrapolateRight: 'clamp' });
  }

  // Exit transforms
  let exitTransform = '';
  let exitOpacity = 1;

  if (exitType === 'flipOut' && exitProgress > 0) {
    const rotateX = interpolate(exitProgress, [0, 1], [0, -60]);
    const scale = interpolate(exitProgress, [0, 1], [1, 0.9]);
    exitTransform = `rotateX(${rotateX}deg) scale(${scale})`;
    exitOpacity = interpolate(exitProgress, [0, 1], [1, 0]);
  } else if (exitType === 'fadeOut' && exitProgress > 0) {
    const scale = interpolate(exitProgress, [0, 1], [1, 1.05]);
    exitTransform = `scale(${scale})`;
    exitOpacity = interpolate(exitProgress, [0, 1], [1, 0]);
  }

  const finalOpacity = entranceOpacity * exitOpacity;
  const finalTransform = exitProgress > 0 ? exitTransform : entranceTransform;

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        perspective: 1200,
      }}
    >
      <div
        style={{
          width: '100%',
          height: '100%',
          transform: finalTransform,
          opacity: finalOpacity,
          transformOrigin: 'center center',
        }}
      >
        {children}
      </div>
    </div>
  );
};
