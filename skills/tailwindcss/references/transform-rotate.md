---
name: transform-rotate
description: Rotating elements in 2D and 3D space with degree values and custom rotations
---

# Rotate

Utilities for rotating elements.

## Usage

### 2D rotation

Use `rotate-<number>` to rotate by degrees:

```html
<div class="rotate-45">45 degrees</div>
<div class="rotate-90">90 degrees</div>
<div class="-rotate-45">-45 degrees (counterclockwise)</div>
```

### 3D rotation

Use `rotate-x-<number>`, `rotate-y-<number>`, `rotate-z-<number>` for 3D rotation:

```html
<div class="rotate-x-50 rotate-z-45">3D rotation</div>
<div class="rotate-y-25 rotate-z-30">Combined 3D rotation</div>
```

### Common rotations

```html
<div class="rotate-90">Quarter turn</div>
<div class="rotate-180">Half turn</div>
<div class="rotate-270">Three-quarter turn</div>
```

### Custom values

Use arbitrary values for custom rotations:

```html
<div class="rotate-[3.142rad]">Custom radian rotation</div>
<div class="rotate-[45deg]">Explicit degree rotation</div>
```

### Removing rotation

Use `rotate-none` to remove rotation:

```html
<div class="rotate-45 md:rotate-none">Rotated on mobile only</div>
```

## Key Points

- `rotate-*` rotates in 2D plane (around z-axis)
- `rotate-x-*` rotates around x-axis (3D)
- `rotate-y-*` rotates around y-axis (3D)
- `rotate-z-*` rotates around z-axis (3D, same as `rotate-*`)
- Negative values rotate counterclockwise: `-rotate-45`
- Common values: `45`, `90`, `180`, `270` degrees
- Can combine multiple axes: `rotate-x-50 rotate-y-30 rotate-z-45`
- Use `rotate-none` to remove all rotations

<!--
Source references:
- https://tailwindcss.com/docs/rotate
-->
