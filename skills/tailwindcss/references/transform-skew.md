---
name: transform-skew
description: Skewing elements on x and y axes with degree values
---

# Skew

Utilities for skewing (distorting) elements.

## Usage

### Skewing both axes

Use `skew-<number>` to skew on both axes:

```html
<div class="skew-3">Slight skew</div>
<div class="skew-6">Moderate skew</div>
<div class="skew-12">Strong skew</div>
```

### Axis-specific skewing

Use `skew-x-<number>` or `skew-y-<number>` to skew on one axis:

```html
<div class="skew-x-12">Skewed horizontally</div>
<div class="skew-y-6">Skewed vertically</div>
```

### Negative skewing

Use negative values for opposite direction:

```html
<div class="-skew-3">Negative skew</div>
<div class="-skew-x-12">Negative x-axis skew</div>
```

### Custom values

Use arbitrary values for custom skew:

```html
<div class="skew-[3.142rad]">Custom radian skew</div>
<div class="skew-x-[15deg]">Custom degree skew</div>
```

## Key Points

- `skew-*` skews on both x and y axes
- `skew-x-*` skews horizontally only
- `skew-y-*` skews vertically only
- Values are in degrees: `skew-3` = 3 degrees
- Negative values skew in opposite direction
- Common values: `3`, `6`, `12` degrees for subtle effects
- Use sparingly - excessive skewing can make text hard to read

<!--
Source references:
- https://tailwindcss.com/docs/skew
-->
