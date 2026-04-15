---
name: typography-font-text
description: Font size, weight, style, text color, line height, letter spacing, and text decoration
---

# Typography: Font & Text

Utilities for font styling, text color, line height, letter spacing, and decoration.

## Usage

### Font size

```html
<p class="text-xs">Extra small</p>
<p class="text-sm">Small</p>
<p class="text-base">Base (default)</p>
<p class="text-lg">Large</p>
<p class="text-xl">Extra large</p>
<p class="text-2xl">2xl</p>
<p class="text-[17px]">Arbitrary</p>
```

### Font weight

```html
<p class="font-thin">100</p>
<p class="font-light">300</p>
<p class="font-normal">400</p>
<p class="font-medium">500</p>
<p class="font-semibold">600</p>
<p class="font-bold">700</p>
<p class="font-extrabold">800</p>
```

### Font style and family

```html
<p class="italic">Italic</p>
<p class="not-italic">Not italic</p>
<p class="font-sans">Sans (default)</p>
<p class="font-serif">Serif</p>
<p class="font-mono">Monospace</p>
```

### Text color

```html
<p class="text-gray-900">Dark text</p>
<p class="text-blue-500">Blue</p>
<p class="text-red-500/50">50% opacity</p>
<p class="text-[#1da1f2]">Arbitrary color</p>
<p class="text-(--my-color)">CSS variable</p>
```

### Line height

```html
<p class="leading-none">1</p>
<p class="leading-tight">1.25</p>
<p class="leading-normal">1.5</p>
<p class="leading-relaxed">1.625</p>
<p class="leading-loose">2</p>
<p class="leading-[3rem]">Arbitrary</p>
```

### Letter spacing

```html
<p class="tracking-tighter">-0.05em</p>
<p class="tracking-tight">-0.025em</p>
<p class="tracking-normal">0</p>
<p class="tracking-wide">0.025em</p>
<p class="tracking-widest">0.1em</p>
```

### Text decoration

```html
<p class="underline">Underline</p>
<p class="line-through">Strikethrough</p>
<p class="no-underline">Remove</p>
<p class="overline">Overline</p>
<p class="underline decoration-2 underline-offset-4">Custom</p>
```

### Text transform and overflow

```html
<p class="uppercase">UPPERCASE</p>
<p class="lowercase">lowercase</p>
<p class="capitalize">Capitalize Each</p>
<p class="normal-case">Normal</p>

<p class="truncate">Single line ellipsis</p>
<p class="text-ellipsis overflow-hidden">Ellipsis</p>
<p class="line-clamp-3">Clamp to 3 lines</p>
```

## Key Points

- Font size: `text-xs` through `text-9xl`, theme scale
- Weight: `font-thin` to `font-black`
- Color: `text-{color}-{shade}`, opacity modifier `/50`, arbitrary `text-[#hex]`
- Line height: `leading-none`, `leading-tight`, `leading-normal`, `leading-loose`
- Letter spacing: `tracking-tighter` to `tracking-widest`
- Decoration: `underline`, `line-through`, `no-underline`, `decoration-*`, `underline-offset-*`
- Overflow: `truncate` (ellipsis), `line-clamp-{n}`

<!--
Source references:
- https://tailwindcss.com/docs/font-size
- https://tailwindcss.com/docs/font-weight
- https://tailwindcss.com/docs/text-color
- https://tailwindcss.com/docs/line-height
- https://tailwindcss.com/docs/letter-spacing
- https://tailwindcss.com/docs/text-decoration
-->
