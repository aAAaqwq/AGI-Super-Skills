---
name: transform-scale
description: Scaling elements uniformly or on specific axes with percentage values
---

# Scale

Utilities for scaling elements.

## Usage

### Uniform scaling

Use `scale-<number>` to scale on both axes (number represents percentage):

```html
<div class="scale-75">75% size</div>
<div class="scale-100">100% size (default)</div>
<div class="scale-125">125% size</div>
<div class="scale-150">150% size</div>
```

### Axis-specific scaling

Use `scale-x-<number>` or `scale-y-<number>` to scale on one axis:

```html
<div class="scale-x-75">75% width</div>
<div class="scale-y-125">125% height</div>
```

### Negative scaling

Use negative values to mirror and scale:

```html
<div class="-scale-x-100">Mirrored horizontally</div>
<div class="-scale-y-100">Mirrored vertically</div>
<div class="-scale-100">Mirrored both axes</div>
```

### Hover effects

Common pattern for interactive scaling:

```html
<div class="scale-95 hover:scale-100 transition-transform">
  Grows on hover
</div>
```

### Removing scale

Use `scale-none` to remove scaling:

```html
<div class="scale-125 md:scale-none">Scaled on mobile only</div>
```

### Custom values

Use arbitrary values for custom scaling:

```html
<div class="scale-[1.7]">Custom scale value</div>
<div class="scale-x-[0.8]">Custom x-axis scale</div>
```

## Key Points

- `scale-*` scales uniformly on both axes
- `scale-x-*` scales horizontally only
- `scale-y-*` scales vertically only
- Values represent percentages: `scale-75` = 75%, `scale-125` = 125%
- `scale-100` is the default (no scaling)
- Negative values mirror the element: `-scale-x-100` flips horizontally
- Common for hover effects: `hover:scale-110`, `active:scale-95`
- Use `scale-none` to remove all scaling

<!--
Source references:
- https://tailwindcss.com/docs/scale
-->
