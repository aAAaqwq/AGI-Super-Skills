---
name: visual-background
description: Background color, gradient, image, and attachment utilities
---

# Background

Utilities for background color, gradients, images, and attachment.

## Usage

### Background color

```html
<div class="bg-white">White</div>
<div class="bg-gray-100">Light gray</div>
<div class="bg-blue-500">Blue</div>
<div class="bg-sky-500/50">50% opacity</div>
<div class="bg-[#1da1f2]">Arbitrary</div>
<div class="bg-(--my-bg)">CSS variable</div>
```

Color palette follows theme (red, orange, amber, yellow, lime, green, emerald, teal, cyan, sky, blue, indigo, violet, purple, fuchsia, pink, rose, slate, gray, zinc, neutral, stone).

### Background image and gradient

```html
<div class="bg-gradient-to-r from-blue-500 to-purple-600">Linear gradient</div>
<div class="bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500">Multi-stop</div>

<div class="bg-[url('/img/hero.jpg')]">Image</div>
<div class="bg-[url('/img/hero.jpg')] bg-cover bg-center">Image with size/position</div>
```

Gradient directions: `to-t`, `to-tr`, `to-r`, `to-br`, `to-b`, `to-bl`, `to-l`, `to-tl`.

### Background size and position

```html
<div class="bg-auto">auto</div>
<div class="bg-cover">cover</div>
<div class="bg-contain">contain</div>

<div class="bg-center">center</div>
<div class="bg-top">top</div>
<div class="bg-bottom">bottom</div>
<div class="bg-left">left</div>
<div class="bg-right">right</div>
<div class="bg-[position:2rem_2rem]">Arbitrary</div>
```

### Background repeat and attachment

```html
<div class="bg-repeat">repeat (default)</div>
<div class="bg-no-repeat">no-repeat</div>
<div class="bg-repeat-x">repeat-x</div>

<div class="bg-fixed">fixed (parallax)</div>
<div class="bg-local">local</div>
<div class="bg-scroll">scroll</div>
```

## Key Points

- Colors: `bg-{color}-{shade}`, opacity `/50`, arbitrary `bg-[#hex]`
- Gradients: `bg-gradient-to-{dir}`, `from-*`, `via-*`, `to-*`
- Image: `bg-[url('...')]`, `bg-cover`, `bg-center`, etc.
- Size: `bg-auto`, `bg-cover`, `bg-contain`
- Position: `bg-center`, `bg-top`, `bg-[position:...]`

<!--
Source references:
- https://tailwindcss.com/docs/background-color
- https://tailwindcss.com/docs/background-image
-->
