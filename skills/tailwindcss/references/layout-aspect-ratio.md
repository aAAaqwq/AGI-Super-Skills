---
name: layout-aspect-ratio
description: Controlling element aspect ratio for responsive media
---

# Aspect Ratio

Utilities for controlling the aspect ratio of an element (e.g. video, images).

## Usage

```html
<!-- 16:9 video container -->
<div class="aspect-video">
  <iframe src="..."></iframe>
</div>

<!-- 4:3 -->
<div class="aspect-[4/3]">Content</div>

<!-- Square -->
<div class="aspect-square">1:1</div>

<!-- Auto (intrinsic) -->
<div class="aspect-auto">Natural ratio</div>
```

## Key Points

- `aspect-video` - 16:9
- `aspect-square` - 1:1
- `aspect-auto` - browser default (intrinsic)
- `aspect-[4/3]` - arbitrary ratio
- Useful for responsive video embeds and image containers

<!--
Source references:
- https://tailwindcss.com/docs/aspect-ratio
-->
