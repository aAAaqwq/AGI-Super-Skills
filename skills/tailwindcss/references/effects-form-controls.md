---
name: effects-form-controls
description: Form control styling with accent-color, appearance, caret-color, and resize
---

# Form Controls & Input Styling

Utilities for styling form controls: accent color, native appearance, caret color, and resize behavior.

## Usage

### Accent color

Control the accent color of checkboxes, radio buttons, range inputs, and progress:

```html
<input type="checkbox" class="accent-pink-500" checked />
<input type="radio" class="accent-rose-500" name="opt" />
<input type="range" class="accent-indigo-500" />

<!-- Opacity modifier -->
<input type="checkbox" class="accent-purple-500/75" />
```

### Appearance

Remove native form control styling for custom designs:

```html
<!-- Custom select with overlay icon -->
<div class="grid">
  <select class="col-start-1 row-start-1 appearance-none bg-gray-50 ...">
    <option>Yes</option>
  </select>
  <svg class="pointer-events-none col-start-1 row-start-1 ...">...</svg>
</div>

<!-- Restore default in forced-colors mode (accessibility) -->
<input type="checkbox" class="appearance-none forced-colors:appearance-auto" />
```

### Caret color

Set the text input cursor color:

```html
<textarea class="caret-pink-500">Focus to see caret</textarea>
<input class="caret-blue-500" />
```

### Resize

Control textarea resize behavior:

```html
<textarea class="resize-y">Vertical only</textarea>
<textarea class="resize-x">Horizontal only</textarea>
<textarea class="resize">Both directions</textarea>
<textarea class="resize-none">No resize handle</textarea>
```

## Key Points

- `accent-*` - theme colors for checkboxes, radio, range; use `accent-[#hex]` or `accent-(--var)` for custom
- `appearance-none` - remove native styling (custom selects, checkboxes)
- `appearance-auto` - restore default (e.g. for `forced-colors: active`)
- `caret-*` - theme colors for input cursor; matches text color patterns
- `resize` - both; `resize-x` - horizontal; `resize-y` - vertical; `resize-none` - no handle

<!--
Source references:
- https://tailwindcss.com/docs/accent-color
- https://tailwindcss.com/docs/appearance
- https://tailwindcss.com/docs/caret-color
- https://tailwindcss.com/docs/resize
-->
