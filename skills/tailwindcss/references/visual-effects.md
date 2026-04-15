---
name: visual-effects
description: Box shadow, opacity, mix-blend, and filter effects
---

# Effects

Utilities for box shadow, opacity, mix-blend, and filters.

## Usage

### Box shadow

```html
<div class="shadow-sm">Small</div>
<div class="shadow">Default</div>
<div class="shadow-md">Medium</div>
<div class="shadow-lg">Large</div>
<div class="shadow-xl">Extra large</div>
<div class="shadow-2xl">2xl</div>
<div class="shadow-none">None</div>

<div class="shadow-lg shadow-blue-500/50">Colored shadow</div>
<div class="shadow-[0_0_15px_rgba(0,0,0,0.2)]">Arbitrary</div>
```

### Opacity

```html
<div class="opacity-0">Invisible</div>
<div class="opacity-50">50%</div>
<div class="opacity-100">Full</div>
```

### Mix blend mode

```html
<div class="mix-blend-normal">Normal</div>
<div class="mix-blend-multiply">Multiply</div>
<div class="mix-blend-screen">Screen</div>
<div class="mix-blend-overlay">Overlay</div>
```

### Backdrop blur and filter

```html
<div class="backdrop-blur-sm">Blur backdrop</div>
<div class="backdrop-blur-md">Medium blur</div>
<div class="backdrop-blur-none">No blur</div>

<div class="backdrop-opacity-50">Backdrop opacity</div>
```

### Filter (blur, brightness, contrast, etc.)

```html
<div class="blur-sm">Blur</div>
<div class="brightness-90">Brightness</div>
<div class="contrast-125">Contrast</div>
<div class="grayscale">Grayscale</div>
<div class="invert">Invert</div>
<div class="sepia">Sepia</div>
<div class="blur-none">No filter</div>
```

### Object fit (images/video)

```html
<img class="object-contain" /> <!-- Fit within bounds -->
<img class="object-cover" />   <!-- Cover area, may crop -->
<img class="object-fill" />    <!-- Stretch -->
<img class="object-none" />    <!-- No resize -->
<img class="object-scale-down" /> <!-- contain or none, whichever is smaller -->
<img class="object-top object-cover" /> <!-- Position -->
```

## Key Points

- Shadow: `shadow-{size}`, `shadow-{color}/opacity`, `shadow-none`
- Opacity: `opacity-{0-100}`
- Mix blend: `mix-blend-{mode}`
- Backdrop: `backdrop-blur-*`, `backdrop-opacity-*`
- Filter: `blur-*`, `brightness-*`, `contrast-*`, `grayscale`, `invert`, `sepia`

<!--
Source references:
- https://tailwindcss.com/docs/box-shadow
- https://tailwindcss.com/docs/opacity
- https://tailwindcss.com/docs/backdrop-blur
-->
