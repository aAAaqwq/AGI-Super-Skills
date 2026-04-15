---
name: layout-min-max-sizing
description: Setting minimum and maximum width and height with min-w, max-w, min-h, max-h
---

# Min & Max Sizing

Utilities for constraining element dimensions with minimum and maximum width/height.

## Usage

### Min width

```html
<!-- Spacing scale -->
<div class="min-w-24">min-w-24</div>
<div class="min-w-64">min-w-64</div>

<!-- Percentage -->
<div class="min-w-full">min-w-full</div>
<div class="min-w-3/4">min-w-3/4</div>

<!-- Container scale -->
<div class="min-w-sm">min-w-sm</div>
<div class="min-w-xl">min-w-xl</div>

<!-- Content-based -->
<div class="min-w-min">min-content</div>
<div class="min-w-max">max-content</div>
<div class="min-w-fit">fit-content</div>
<div class="min-w-auto">auto</div>

<!-- Custom -->
<div class="min-w-[220px]">Custom</div>
```

### Max width

Use `max-w-<value>` with similar scales: spacing numbers, fractions (`max-w-1/2`), container sizes (`max-w-md`), `max-w-full`, `max-w-screen`, `max-w-min`, `max-w-max`, `max-w-fit`, `max-w-none`.

### Min / Max height

```html
<div class="min-h-screen">At least full viewport height</div>
<div class="min-h-0">Allow shrinking in flex</div>
<div class="max-h-96 overflow-y-auto">Scrollable with max height</div>
```

## Key Points

- min-w: spacing scale, fractions, container scale (3xs–7xl), `full`, `screen`, `min`, `max`, `fit`, `auto`
- max-w: same options plus `none`
- min-h / max-h: similar scales; `min-h-0` important for flex children to shrink
- Viewport units: `min-w-screen`, `min-w-dvw`, `min-w-svw`, `min-w-lvw`
- Container scale: `min-w-3xs` through `min-w-7xl` map to `--container-*` variables

<!--
Source references:
- https://tailwindcss.com/docs/min-width
- https://tailwindcss.com/docs/max-width
- https://tailwindcss.com/docs/min-height
- https://tailwindcss.com/docs/max-height
-->
