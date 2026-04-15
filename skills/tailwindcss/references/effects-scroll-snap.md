---
name: effects-scroll-snap
description: CSS scroll snap for carousels and scroll containers
---

# Scroll Snap

Utilities for scroll snap behavior in overflow containers. Use for carousels, horizontal galleries, or paged scroll.

## Usage

### Container

```html
<!-- Horizontal snap (carousel) -->
<div class="snap-x snap-mandatory overflow-x-auto flex gap-4">
  <div class="snap-center shrink-0 w-80">Slide 1</div>
  <div class="snap-center shrink-0 w-80">Slide 2</div>
  <div class="snap-center shrink-0 w-80">Slide 3</div>
</div>

<!-- Vertical snap -->
<div class="snap-y snap-mandatory overflow-y-auto h-screen">
  <div class="snap-start h-screen">Section 1</div>
  <div class="snap-start h-screen">Section 2</div>
</div>

<!-- Both axes -->
<div class="snap-both overflow-auto">...</div>
```

### Strictness

- `snap-mandatory` - always rest on a snap point
- `snap-proximity` - snap only when close to a point (default)

### Child alignment

```html
<div class="snap-x overflow-x-auto">
  <div class="snap-center">Center snap</div>
  <div class="snap-start">Start snap</div>
  <div class="snap-end">End snap</div>
  <div class="snap-align-none">No snap</div>
</div>
```

## Key Points

- `snap-x` - horizontal; `snap-y` - vertical; `snap-both` - both; `snap-none` - disable
- `snap-mandatory` / `snap-proximity` - strictness
- Child: `snap-center`, `snap-start`, `snap-end`, `snap-align-none`
- Requires overflow (e.g. `overflow-x-auto`) and scroll on container

<!--
Source references:
- https://tailwindcss.com/docs/scroll-snap-type
- https://tailwindcss.com/docs/scroll-snap-align
-->
