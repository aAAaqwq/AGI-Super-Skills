import { Composition } from "remotion";
import { AIResearchSkillsPromo } from "./AIResearchSkillsPromo";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="AIResearchSkillsPromo"
        component={AIResearchSkillsPromo}
        durationInFrames={465} // ~15.5 seconds at 30fps
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
