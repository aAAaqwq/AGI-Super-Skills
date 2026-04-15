---
name: visual-svg
description: Styling SVG elements with fill, stroke, and stroke-width utilities
---

# SVG Styling

Utilities for styling SVG fill and stroke. Essential when working with icon sets like Heroicons.

## Usage

### Fill

```html
<!-- Theme colors -->
<svg class="fill-blue-500">...</svg>
<svg class="fill-indigo-500 hover:fill-indigo-600">...</svg>

<!-- Inherit from text color -->
<button class="text-indigo-600 hover:text-white">
  <svg class="size-5 fill-current">...</svg>
  Check for updates
</button>

<!-- Special values -->
<svg class="fill-none">...</svg>
<svg class="fill-inherit">...</svg>
<svg class="fill-transparent">...</svg>

<!-- Custom -->
<svg class="fill-[#243c5a]">...</svg>
<svg class="fill-(--my-fill)">...</svg>
```

### Stroke

```html
<!-- Theme colors -->
<svg class="stroke-cyan-500" fill="none">...</svg>

<!-- Inherit from text -->
<button class="text-pink-600 hover:text-white">
  <svg class="size-5 stroke-current" fill="none">...</svg>
  Download
</button>

<!-- Special values -->
<svg class="stroke-none stroke-inherit stroke-transparent">...</svg>
```

### Stroke width

```html
<svg class="stroke-1">Thin stroke</svg>
<svg class="stroke-2">Medium stroke</svg>
<svg class="stroke-[1.5]">Custom width</svg>
<svg class="stroke-(length:--my-stroke)">Custom property</svg>
```

### Combined

```html
<svg class="size-6 fill-blue-500 stroke-blue-700 stroke-2" fill="none">
  <!-- Outlined icon with colored stroke -->
</svg>
```

## Key Points

- `fill-*` / `stroke-*` - all theme colors (e.g. `fill-red-500`)
- `fill-current` / `stroke-current` - use current text color (common for icons in buttons)
- `fill-none` / `stroke-none` - no fill/stroke
- `stroke-1`, `stroke-2`, etc. - stroke width (number = px)
- Custom: `fill-[#hex]`, `stroke-(--var)`, `stroke-[1.5]`
- Use with variants: `hover:fill-blue-600`, `md:stroke-2`

<!--
Source references:
- https://tailwindcss.com/docs/fill
- https://tailwindcss.com/docs/stroke
- https://tailwindcss.com/docs/stroke-width
-->
