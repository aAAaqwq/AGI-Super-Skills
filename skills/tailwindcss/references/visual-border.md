---
name: visual-border
description: Border width, color, style, and border radius
---

# Border

Utilities for border width, color, style, and radius.

## Usage

### Border width

```html
<div class="border">1px all sides</div>
<div class="border-2">2px</div>
<div class="border-0">No border</div>

<div class="border-t border-r border-b border-l">Per side</div>
<div class="border-x-2">Horizontal</div>
<div class="border-y">Vertical</div>
```

### Border color

```html
<div class="border border-gray-300">Gray border</div>
<div class="border-2 border-blue-500">Blue</div>
<div class="border border-red-500/50">With opacity</div>
```

### Border style

```html
<div class="border border-solid">Solid (default)</div>
<div class="border border-dashed">Dashed</div>
<div class="border border-dotted">Dotted</div>
<div class="border border-double">Double</div>
<div class="border border-none">None</div>
```

### Border radius

```html
<div class="rounded">Small (default)</div>
<div class="rounded-sm">2px</div>
<div class="rounded-md">6px</div>
<div class="rounded-lg">8px</div>
<div class="rounded-xl">12px</div>
<div class="rounded-2xl">16px</div>
<div class="rounded-full">Pill/circle</div>
<div class="rounded-none">0</div>

<div class="rounded-t-lg rounded-b-none">Per corner</div>
<div class="rounded-s-md rounded-e-xl">Logical (start/end)</div>
```

### Divide (between children)

```html
<div class="divide-y divide-gray-200">
  <div>Item 1</div>
  <div>Item 2</div>
  <div>Item 3</div>
</div>
<div class="divide-x divide-gray-300 flex">
  <div>Col 1</div>
  <div>Col 2</div>
</div>
```

### Ring (focus outline)

```html
<button class="ring-2 ring-blue-500 ring-offset-2">Ring</button>
<button class="focus:ring-3 focus:ring-blue-500">Focus ring</button>
```

### Outline

Separate from border; used for focus states. In v4: `outline` = 1px; `outline-2`, `outline-4` for width. Use `outline-offset-2` for offset.

```html
<button class="outline outline-offset-2 outline-sky-500">Outline</button>
<button class="focus:outline-2 focus:outline-cyan-500">Focus outline</button>
<!-- Accessibility: invisible but visible in forced-colors -->
<button class="focus:outline-hidden">Focus outline-hidden</button>
```

v4: `outline-none` = `outline-style: none`; `outline-hidden` = invisible but shows in forced-colors mode.

## Key Points

- Width: `border`, `border-{0,2,4,8}`, `border-{t,r,b,l,x,y}`
- Color: `border-{color}`, opacity modifier
- Radius: `rounded-{size}`, `rounded-full`, `rounded-{t,r,b,l,s,e}-*`, logical `rounded-s-*`, `rounded-e-*`
- Divide: `divide-{x,y}`, `divide-{color}` for borders between flex/grid children
- Ring: `ring`, `ring-{n}`, `ring-{color}`, `ring-offset-{n}` (v4 default ring = 1px; use `ring-3` for 3px)
- Outline: `outline`, `outline-{n}`, `outline-{color}`, `outline-offset-{n}`, `outline-hidden`, `outline-none`

<!--
Source references:
- https://tailwindcss.com/docs/border-width
- https://tailwindcss.com/docs/border-color
- https://tailwindcss.com/docs/border-radius
- https://tailwindcss.com/docs/divide-width
- https://tailwindcss.com/docs/ring-width
-->
