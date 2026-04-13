---
name: video-caption-burner
description: Burn existing subtitles or captions directly into video exports so they remain visible across platforms and players. Use when a team already has captions and needs a platform-ready, subtitle-baked video for social, ads, storefronts, or review links.
---

# Video Caption Burner

Burn captions into the video itself so they stay visible everywhere.

## Problem it solves
A lot of teams already have subtitle text, SRT files, or caption timing—but still lose time because playback environments don’t reliably show captions. This skill takes existing captions and bakes them into the video so the final export is consistent across platforms, players, and review workflows.

## Use when
- A team already has captions and wants them permanently visible
- A platform or delivery channel handles subtitle tracks badly
- A social, ad, storefront, or review export needs captioned playback by default
- The user wants styled hardcoded subtitles instead of optional subtitle files

## Do not use when
- The user still needs transcription or caption generation from audio
- The team wants captions to remain separately editable at playback time
- Subtitle timing is incomplete or unreliable and needs repair first

## Inputs
- Source video file
- Existing subtitle file or caption text with timing
- Caption style preference: clean, bold, social, storefront-safe, etc.
- Optional placement, font-size, color, background, and line-length constraints
- Target platform or use case

## Workflow
1. Confirm captions already exist and do not need transcription.
2. Choose a caption style appropriate for the destination.
3. Burn the captions into the frame while protecting readability.
4. Check for collisions with faces, products, demos, or key UI areas.
5. Export the final captioned video with style notes.

## Output
Return:
1. Caption burn-in plan
2. Style choice
3. Placement notes
4. Readability risks
5. Final export recommendation

## Quality bar
- Prioritize readability over decorative styling
- Avoid placing captions over critical product or face areas
- Keep line lengths manageable for mobile viewing
- Make captions feel native to the platform, not pasted on

## Resource
See `references/output-template.md`.
