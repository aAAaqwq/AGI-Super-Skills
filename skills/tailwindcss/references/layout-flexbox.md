---
name: layout-flexbox
description: Flexbox layout utilities including flex-direction, justify, items, gap, grow, shrink, and wrap
---

# Flexbox

Utilities for building flex layouts: direction, alignment, gap, and item sizing.

## Usage

### Flex direction and wrap

```html
<div class="flex flex-row">Horizontal (default)</div>
<div class="flex flex-row-reverse">Reversed</div>
<div class="flex flex-col">Vertical</div>
<div class="flex flex-col-reverse">Vertical reversed</div>

<div class="flex flex-wrap">Wrap when needed</div>
<div class="flex flex-nowrap">No wrap (default)</div>
<div class="flex flex-wrap-reverse">Wrap reversed</div>
```

### Justify content

```html
<div class="flex justify-start">Start</div>
<div class="flex justify-end">End</div>
<div class="flex justify-center">Center</div>
<div class="flex justify-between">Space between</div>
<div class="flex justify-around">Space around</div>
<div class="flex justify-evenly">Space evenly</div>
```

### Align items

```html
<div class="flex items-start">Align start</div>
<div class="flex items-end">Align end</div>
<div class="flex items-center">Center (common)</div>
<div class="flex items-baseline">Baseline</div>
<div class="flex items-stretch">Stretch (default)</div>
```

### Align self (on flex children)

```html
<div class="flex">
  <div class="self-auto">Auto</div>
  <div class="self-start">Start</div>
  <div class="self-center">Center</div>
  <div class="self-stretch">Stretch</div>
</div>
```

### Gap

```html
<div class="flex gap-4">gap-4 (1rem)</div>
<div class="flex gap-x-2 gap-y-4">Different x/y gap</div>
<div class="flex gap-0">No gap</div>
```

### Flex grow, shrink, basis

```html
<div class="flex">
  <div class="w-14 flex-none">Fixed</div>
  <div class="flex-1">Grows and shrinks</div>
  <div class="flex-initial">Shrink only</div>
  <div class="flex-auto">Grow/shrink with initial size</div>
</div>
```

- `flex-1` = `flex: 1 1 0%` - equal distribution
- `flex-initial` = `flex: 0 1 auto` - shrink, don't grow
- `flex-auto` = `flex: 1 1 auto` - grow/shrink from content size
- `flex-none` = `flex: none` - no grow or shrink

### Order

```html
<div class="flex">
  <div class="order-2">Second</div>
  <div class="order-1">First</div>
  <div class="order-last">Last</div>
</div>
```

## Key Points

- Use `flex` or `inline-flex` as container (see layout-display)
- Direction: `flex-row`, `flex-col`, `flex-row-reverse`, `flex-col-reverse`
- Justify: `justify-start`, `justify-center`, `justify-between`, `justify-evenly`
- Align: `items-center`, `items-start`, `items-stretch`
- Gap: `gap-{n}`, `gap-x-{n}`, `gap-y-{n}` (spacing scale)
- Item sizing: `flex-1`, `flex-none`, `flex-auto`, `flex-initial`
- Self alignment: `self-center`, `self-start`, etc.
- Order: `order-{n}`, `order-first`, `order-last`

<!--
Source references:
- https://tailwindcss.com/docs/flex-direction
- https://tailwindcss.com/docs/justify-content
- https://tailwindcss.com/docs/align-items
- https://tailwindcss.com/docs/gap
- https://tailwindcss.com/docs/flex
- https://tailwindcss.com/docs/order
-->
