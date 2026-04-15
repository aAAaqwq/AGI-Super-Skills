---
name: layout-overflow
description: Controlling how elements handle content that overflows their container
---

# Overflow

Utilities for controlling how an element handles content that is too large for the container.

## Usage

### Basic overflow

Use `overflow-auto`, `overflow-hidden`, `overflow-visible`, `overflow-scroll`:

```html
<div class="overflow-auto">Scrolls if needed</div>
<div class="overflow-hidden">Clips overflow</div>
<div class="overflow-visible">Shows overflow</div>
<div class="overflow-scroll">Always shows scrollbars</div>
```

### Axis-specific overflow

Use `overflow-x-*` or `overflow-y-*` for horizontal/vertical control:

```html
<div class="overflow-x-auto overflow-y-hidden">
  Horizontal scroll, vertical clip
</div>
<div class="overflow-x-scroll overflow-y-auto">
  Horizontal always scrolls, vertical scrolls if needed
</div>
```

### Overflow clip

Use `overflow-clip` for clip behavior (similar to hidden but different scroll behavior):

```html
<div class="overflow-clip">Clips without creating scroll container</div>
```

## Key Points

- `overflow-auto` - shows scrollbars only when needed
- `overflow-hidden` - clips content that overflows
- `overflow-visible` - allows content to overflow (default for most elements)
- `overflow-scroll` - always shows scrollbars
- `overflow-clip` - clips without creating scroll container
- Use `overflow-x-*` and `overflow-y-*` for axis-specific control
- Common pattern: `overflow-hidden` for images, `overflow-auto` for scrollable content

<!--
Source references:
- https://tailwindcss.com/docs/overflow
-->
