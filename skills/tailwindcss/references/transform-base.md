---
name: transform-base
description: Base transform utilities for enabling transforms, hardware acceleration, and custom transform values
---

# Transform

Base utilities for transforming elements.

## Usage

### Hardware acceleration

Use `transform-gpu` to force GPU acceleration for better performance:

```html
<div class="scale-150 transform-gpu">
  GPU-accelerated transform
</div>
```

### CPU rendering

Use `transform-cpu` to force CPU rendering if needed:

```html
<div class="scale-150 transform-cpu">
  CPU-rendered transform
</div>
```

### Removing transforms

Use `transform-none` to remove all transforms:

```html
<div class="skew-y-3 md:transform-none">
  Skewed on mobile, normal on desktop
</div>
```

### Custom transforms

Use arbitrary values for custom transform functions:

```html
<div class="transform-[matrix(1,2,3,4,5,6)]">
  Custom matrix transform
</div>
<div class="transform-[perspective(1000px)_rotateX(45deg)]">
  Custom 3D transform
</div>
```

## Key Points

- `transform-gpu` enables hardware acceleration with `translateZ(0)`
- `transform-cpu` forces CPU rendering (removes GPU acceleration)
- `transform-none` removes all transforms at once
- Use `transform-gpu` for better animation performance
- Custom transforms use arbitrary values: `transform-[...]`
- Transform utilities (translate, rotate, scale, skew) automatically enable transform
- Hardware acceleration is usually beneficial for animations

<!--
Source references:
- https://tailwindcss.com/docs/transform
-->
