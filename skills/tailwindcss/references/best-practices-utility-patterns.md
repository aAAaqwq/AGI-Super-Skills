---
name: best-practices-utility-patterns
description: Managing duplication, conflicts, important modifier, and when to use components
---

# Best Practices: Utility Patterns

Practical patterns when building with Tailwind utilities.

## Managing duplication

**Use components** for repeated UI: Extract into React/Vue/Svelte components or template partials.

```jsx
function Button({ children, variant = 'primary' }) {
  const base = 'px-4 py-2 rounded-lg font-medium'
  const variants = {
    primary: 'bg-blue-500 hover:bg-blue-600 text-white',
    secondary: 'bg-gray-200 hover:bg-gray-300 text-gray-900',
  }
  return <button className={`${base} ${variants[variant]}`}>{children}</button>
}
```

**Use loops** when markup is repeated from data—the class list is written once.

**Multi-cursor editing** for localized duplication in a single file.

## Managing conflicts

When two utilities target the same property, the one **later in the stylesheet** wins. Avoid adding conflicting classes:

```html
<!-- Bad -->
<div class="flex grid">Conflict</div>

<!-- Good: conditional class -->
<div class={gridLayout ? 'grid' : 'flex'}>
```

## Important modifier

Add `!` suffix to force `!important`:

```html
<div class="bg-teal-500 bg-red-500!">Red wins</div>
```

Use sparingly; prefer fixing specificity properly.

## Important flag (global)

```css
@import "tailwindcss" important;
```

Makes all utilities `!important`. Useful when integrating into existing high-specificity CSS.

## Prefix option

```css
@import "tailwindcss" prefix(tw);
```

Generates `tw:text-red-500` etc. Use when project class names conflict with Tailwind.

## When to use inline styles

- Values from API/database (e.g. brand colors)
- Dynamic values that change at runtime
- Complex arbitrary values hard to read as class names
- Pattern: set CSS variables via inline style, reference with `bg-(--my-var)`

## Key Points

- Extract repeated patterns into components
- Never add two conflicting utilities—use conditional classes
- `!` suffix = single utility `!important`
- `important` flag = all utilities `!important`
- `prefix(tw)` = prefix all utilities
- Use inline styles for dynamic values; utilities for static design

<!--
Source references:
- https://tailwindcss.com/docs/utility-first#managing-duplication
- https://tailwindcss.com/docs/utility-first#managing-style-conflicts
-->
