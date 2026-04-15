---
name: layout-object-fit-position
description: Controlling how replaced elements (images, video) are resized and positioned within their container
---

# Object Fit & Object Position

Utilities for controlling how replaced elements like `<img>` and `<video>` are resized and positioned within their container.

## Usage

### Object fit

```html
<!-- Cover container, may crop -->
<img class="h-48 w-96 object-cover" src="photo.jpg" />

<!-- Contain within, may letterbox -->
<img class="h-48 w-96 object-contain" src="photo.jpg" />

<!-- Stretch to fill -->
<img class="h-48 w-96 object-fill" src="photo.jpg" />

<!-- Scale down only if needed, else original size -->
<img class="h-48 w-96 object-scale-down" src="photo.jpg" />

<!-- Original size, ignore container -->
<img class="h-48 w-96 object-none" src="photo.jpg" />
```

### Object position

```html
<!-- Named positions -->
<img class="size-24 object-cover object-top-left" src="photo.jpg" />
<img class="size-24 object-cover object-center" src="photo.jpg" />
<img class="size-24 object-cover object-bottom-right" src="photo.jpg" />

<!-- Custom value -->
<img class="object-cover object-[25%_75%]" src="photo.jpg" />
<img class="object-(--my-object)" src="photo.jpg" />
```

### Responsive

```html
<img class="object-contain md:object-cover object-center md:object-top" src="photo.jpg" />
```

## Key Points

- `object-contain` - maintain aspect ratio, fit inside container
- `object-cover` - maintain aspect ratio, cover container (may crop)
- `object-fill` - stretch to fill container
- `object-scale-down` - like `contain` but never upscale
- `object-none` - original size, ignore container
- Position: `object-top-left`, `object-top`, `object-top-right`, `object-left`, `object-center`, `object-right`, `object-bottom-left`, `object-bottom`, `object-bottom-right`
- Custom: `object-[25%_75%]`, `object-(--custom-property)`

<!--
Source references:
- https://tailwindcss.com/docs/object-fit
- https://tailwindcss.com/docs/object-position
-->
