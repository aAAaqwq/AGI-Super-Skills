## Description: <br>
Convert Markdown to WeChat Official Account HTML, inspect supported providers/themes/prompts, generate article images, create drafts, write with creator styles, and remove AI writing traces. <br>

This skill is ready for commercial/non-commercial use. <br>

## Publisher: <br>
[geekjourneyx](https://clawhub.ai/user/geekjourneyx) <br>

### License/Terms of Use: <br>
MIT-0 <br>


## Use Case: <br>
Developers, content teams, and publishing agents use this skill to prepare WeChat Official Account articles, previews, drafts, image posts, and related publishing assets from Markdown and local media. <br>

### Deployment Geography for Use: <br>
Global <br>

## Known Risks and Mitigations: <br>
Risk: The skill uses WeChat Official Account credentials for draft upload and post creation. <br>
Mitigation: Install only from trusted CLI sources, validate configuration, and require explicit user approval before upload, draft creation, image-post creation, or other publish-related actions. <br>
Risk: The skill can call external image-generation services or process private drafts through configured providers. <br>
Mitigation: Review provider and base URL settings before processing private content, and use inspect, preview, dry-run, or local-only flows before remote actions. <br>
Risk: Humanize and creator-style features can be used to obscure AI-written content or imitate identifiable creators. <br>
Mitigation: Avoid misleading readers, hiding required AI disclosure, impersonating creators, or copying identifiable styles without authorization. <br>


## Reference(s): <br>
- [ClawHub skill page](https://clawhub.ai/geekjourneyx/md2wechat) <br>
- [Project homepage](https://github.com/geekjourneyx/md2wechat-skill) <br>


## Skill Output: <br>
**Output Type(s):** [Text, Markdown, Code, Shell commands, Configuration, Guidance] <br>
**Output Format:** [Markdown guidance with inline shell commands and configuration values] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [May produce local HTML previews, generated image prompts or assets, and WeChat draft or image-post commands when explicitly requested.] <br>

## Skill Version(s): <br>
2.0.7 (source: server release metadata) <br>

## Ethical Considerations: <br>
Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment. <br>
