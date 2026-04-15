---
name: layout-height
description: Setting element height with spacing scale, fractions, viewport units, and content-based sizing
---

# Height

Utilities for setting the height of an element.

## Usage

### Spacing scale

Use `h-<number>` utilities based on the spacing scale:

```html
<div class="h-24">h-24</div>
<div class="h-48">h-48</div>
<div class="h-64">h-64</div>
```

### Percentage heights

Use `h-full` or `h-<fraction>` for percentage-based heights:

```html
<div class="h-full">100%</div>
<div class="h-1/2">50%</div>
<div class="h-3/4">75%</div>
<div class="h-9/10">90%</div>
```

### Viewport units

Use `h-screen` for full viewport height, or dynamic viewport units:

```html
<div class="h-screen">Full viewport height (100vh)</div>
<div class="h-dvh">Dynamic viewport height</div>
<div class="h-svh">Small viewport height</div>
<div class="h-lvh">Large viewport height</div>
```

### Content-based heights

Use `h-auto`, `h-fit`, `h-min`, `h-max` for content-based sizing:

```html
<div class="h-auto">Auto height</div>
<div class="h-fit">Fit content</div>
<div class="h-min">Min content</div>
<div class="h-max">Max content</div>
```

### Line height

Use `h-lh` to match line height:

```html
<div class="h-lh">Matches line height</div>
```

### Size utility

Use `size-<number>` to set both width and height:

```html
<div class="size-16">16x16</div>
<div class="size-24">24x24</div>
<div class="size-full">100% x 100%</div>
```

### Custom values

Use arbitrary values for custom heights:

```html
<div class="h-[117px]">Custom pixel height</div>
<div class="h-[50vh]">Custom viewport height</div>
<div class="h-[calc(100vh-2rem)]">Custom calculation</div>
```

## Key Points

- Spacing scale: `h-0` through `h-96` (and beyond)
- Fractions: `h-1/2`, `h-1/3`, `h-2/3`, `h-1/4`, `h-3/4`, `h-9/10`
- Viewport units: `h-screen` (100vh), `h-dvh`, `h-svh`, `h-lvh`
- `h-dvh` adapts to browser UI (address bar, etc.)
- `h-svh` uses smallest viewport height
- `h-lvh` uses largest viewport height
- `size-*` utilities set both width and height simultaneously
- Use `h-auto` to reset height at specific breakpoints

<!--
Source references:
- https://tailwindcss.com/docs/height
-->
