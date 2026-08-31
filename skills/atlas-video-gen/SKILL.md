---
name: atlas-video-gen
description: Generate one Veo 3.1 Lite video through Atlas Cloud. Use when text-to-video needs an Atlas route, explicit paid-request confirmation, bounded polling, and a local MP4.
---

# Atlas Cloud Video Generation

Generate one text-to-video clip with Atlas Cloud's `google/veo3.1-lite/text-to-video`
model. This is an opt-in workflow and does not replace any other video provider.

## Prerequisites

- Python 3.10 or newer; the helper uses only the standard library.
- An Atlas Cloud API key in `ATLASCLOUD_API_KEY`.
- Outbound HTTPS access to `api.atlascloud.ai` and the returned output URL.

Set the key in the environment. Never put it in a prompt, command argument,
source file, or log.

```bash
export ATLASCLOUD_API_KEY="..."
```

## Safety Boundary

Running a generation request may incur charges. The helper prints the exact
request plan and exits without network access unless `--yes` is present.

The generation `POST` is sent exactly once and is never retried. Only prediction
and output `GET` requests use bounded retries for transient failures. If the
submission result is unclear, stop and inspect the Atlas Cloud console instead
of running the command again.

## Usage

Preview the request first:

```bash
python skills/atlas-video-gen/scripts/generate_video.py \
  "A slow aerial orbit around a lighthouse at sunrise" \
  --output lighthouse.mp4
```

After reviewing the plan, confirm one paid submission:

```bash
python skills/atlas-video-gen/scripts/generate_video.py \
  "A slow aerial orbit around a lighthouse at sunrise" \
  --output lighthouse.mp4 \
  --duration 4 \
  --ratio 16:9 \
  --resolution 720p \
  --yes
```

Use `--json` for a machine-readable result. The default timeout is 10 minutes,
and `--poll-interval` controls prediction polling frequency.

## Supported Inputs

| Option | Values | Default |
|---|---|---|
| `--duration` | `4`, `6`, `8` | `8` |
| `--ratio` | `16:9`, `9:16` | `16:9` |
| `--resolution` | `720p`, `1080p` | `720p` |
| `--seed` | integer; `-1` requests a random seed | `-1` |

Atlas Cloud's current schema requires an 8-second duration for `1080p` output.
The helper validates that rule before submitting.

## Workflow

1. Turn the request into a concise English video prompt with subject motion,
   camera movement, setting, lighting, and audio cues when relevant.
2. Preview the helper command without `--yes`.
3. Obtain explicit human approval for the displayed model and parameters.
4. Run once with `--yes`.
5. Wait for terminal prediction status and report the saved MP4 path.
6. On an ambiguous submission or failure, do not resubmit automatically.

## Limitations

- This helper supports text-to-video only. Use a separate image-to-video skill
  when a start or end frame is required.
- Model availability and accepted parameters can change. If Atlas Cloud rejects
  a previously valid request, check the live model catalog and schema before
  changing the helper.
- Generated media remains subject to Atlas Cloud and model content policies.

## Test Evidence

Run the focused standard-library tests with:

```bash
python -m unittest -v skills/atlas-video-gen/scripts/test_generate_video.py
```

The tests cover schema-aligned payloads, the single-POST boundary, wrapped and
flat API responses, preview mode, and the 1080p duration constraint.

## API References

- Model catalog: `https://api.atlascloud.ai/api/v1/models`
- Submit: `POST https://api.atlascloud.ai/api/v1/model/generateVideo`
- Poll: `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`
