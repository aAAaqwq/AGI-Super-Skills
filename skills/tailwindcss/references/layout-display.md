---
name: layout-display
description: Controlling element display type including flex, grid, block, inline, hidden, and sr-only
---

# Display

Utilities for controlling the display box type of an element.

## Usage

### Basic display types

```html
<span class="inline">display: inline</span>
<span class="inline-block">display: inline-block</span>
<div class="block">display: block</div>
```

### Flex and Grid containers

```html
<!-- Flex container -->
<div class="flex items-center gap-4">Flex layout</div>
<span class="inline-flex items-baseline">Inline flex with text</span>

<!-- Grid container -->
<div class="grid grid-cols-3 gap-4">Grid layout</div>
<span class="inline-grid grid-cols-3 gap-4">Inline grid</span>
```

### Flow root

Use `flow-root` to create a block-level element with its own block formatting context (fixes margin collapse):

```html
<div class="flow-root">
  <div class="my-4">Content with isolated BFC</div>
</div>
```

### Contents

Use `contents` for a "phantom" container whose children act like direct children of the parent:

```html
<div class="flex">
  <div class="flex-1">01</div>
  <div class="contents">
    <div class="flex-1">02</div>
    <div class="flex-1">03</div>
  </div>
  <div class="flex-1">04</div>
</div>
```

### Table display

```html
<div class="table w-full">
  <div class="table-header-group bg-gray-100">
    <div class="table-row">
      <div class="table-cell p-2">Header 1</div>
      <div class="table-cell p-2">Header 2</div>
    </div>
  </div>
  <div class="table-row-group">
    <div class="table-row">
      <div class="table-cell p-2">Cell 1</div>
      <div class="table-cell p-2">Cell 2</div>
    </div>
  </div>
</div>
```

### Hidden

```html
<div class="hidden">Removed from document flow</div>
<div class="md:block hidden">Visible only on md+</div>
```

For visual-only hiding while keeping in DOM, use `invisible` or `opacity-0` instead.

### Screen reader only

```html
<a href="#">
  <svg><!-- icon --></svg>
  <span class="sr-only">Settings</span>
</a>
```

Use `not-sr-only` to undo: `<span class="sr-only sm:not-sr-only">Settings</span>`

## Key Points

- `flex` / `inline-flex` - Flexbox layout
- `grid` / `inline-grid` - CSS Grid layout
- `block` / `inline` / `inline-block` - Basic flow
- `hidden` - `display: none` (removes from flow)
- `sr-only` - Visually hidden but accessible to screen readers
- `contents` - Children participate in parent's layout
- `flow-root` - Establishes new BFC
- Table utilities: `table`, `table-row`, `table-cell`, `table-header-group`, etc.

<!--
Source references:
- https://tailwindcss.com/docs/display
-->
