---
name: transform-translate
description: Translating elements on x, y, and z axes with spacing scale, percentages, and custom values
---

# Translate

Utilities for translating (moving) elements.

## Usage

### Spacing scale

Use `translate-<number>` to translate on both axes, or `translate-x-<number>` / `translate-y-<number>` for single axis:

```html
<div class="translate-2">Moved 2 units</div>
<div class="-translate-4">Moved -4 units</div>
<div class="translate-x-4">Moved right 4 units</div>
<div class="translate-y-6">Moved down 6 units</div>
```

### Percentage translation

Use `translate-<fraction>` to translate by percentage of element size:

```html
<div class="translate-1/2">Moved 50% on both axes</div>
<div class="translate-x-1/4">Moved 25% right</div>
<div class="-translate-y-full">Moved 100% up</div>
```

### Centering elements

Common pattern for centering absolutely positioned elements:

```html
<div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
  Centered
</div>
```

### Z-axis translation

Use `translate-z-<number>` for 3D translation (requires `transform-3d` on parent):

```html
<div class="transform-3d">
  <div class="translate-z-4">Forward in 3D space</div>
  <div class="-translate-z-8">Backward in 3D space</div>
</div>
```

### Custom values

Use arbitrary values for custom translations:

```html
<div class="translate-[3.142rad]">Custom translation</div>
<div class="translate-x-[117px]">Custom pixel value</div>
```

## Key Points

- `translate-*` moves on both x and y axes
- `translate-x-*` moves horizontally (right = positive)
- `translate-y-*` moves vertically (down = positive)
- `translate-z-*` moves in 3D space (forward = positive)
- Negative values use dash prefix: `-translate-4`, `-translate-x-8`
- Percentages are relative to element's own size
- Common centering: `top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2`
- Z-axis requires `transform-3d` utility on parent element

<!--
Source references:
- https://tailwindcss.com/docs/translate
-->
