---
name: typography-text-align
description: Controlling text alignment with left, center, right, justify, and logical properties
---

# Text Align

Utilities for controlling the alignment of text.

## Usage

### Basic alignment

Use `text-left`, `text-center`, `text-right`, `text-justify`:

```html
<p class="text-left">Left aligned</p>
<p class="text-center">Center aligned</p>
<p class="text-right">Right aligned</p>
<p class="text-justify">Justified text</p>
```

### Logical properties

Use `text-start` and `text-end` for RTL-aware alignment:

```html
<div dir="ltr">
  <p class="text-start">Left in LTR</p>
  <p class="text-end">Right in LTR</p>
</div>
<div dir="rtl">
  <p class="text-start">Right in RTL</p>
  <p class="text-end">Left in RTL</p>
</div>
```

### Responsive alignment

```html
<p class="text-left md:text-center lg:text-right">
  Responsive alignment
</p>
```

## Key Points

- `text-left` - aligns to left edge
- `text-center` - centers text
- `text-right` - aligns to right edge
- `text-justify` - justifies text (spaces words evenly)
- `text-start` - aligns to start (left in LTR, right in RTL)
- `text-end` - aligns to end (right in LTR, left in RTL)
- Use logical properties (`text-start`, `text-end`) for internationalization
- Common pattern: `text-center` for headings, `text-left` for body text

<!--
Source references:
- https://tailwindcss.com/docs/text-align
-->
