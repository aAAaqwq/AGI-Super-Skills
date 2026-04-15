---
name: features-content-detection
description: How Tailwind detects classes in source files and how to customize content scanning
---

# Detecting Classes in Source Files

Tailwind scans your project for utility classes and generates CSS based on what you've actually used.

## How Classes Are Detected

Tailwind treats all source files as plain text and looks for tokens that could be class names:

```jsx
export function Button({ color, children }) {
  const colors = {
    black: "bg-black text-white",
    blue: "bg-blue-500 text-white",
  };

  return (
    <button className={`${colors[color]} rounded-full px-2 py-1.5`}>
      {children}
    </button>
  );
}
```

Tailwind detects `bg-black`, `text-white`, `bg-blue-500`, `rounded-full`, `px-2`, and `py-1.5` from this file.

## Dynamic Class Names

Tailwind scans files as plain text, so it can't understand string concatenation or interpolation.

### ❌ Don't Construct Classes Dynamically

```html
<div class="text-{{ error ? 'red' : 'green' }}-600"></div>
```

The strings `text-red-600` and `text-green-600` don't exist in the file, so Tailwind won't generate them.

### ✅ Use Complete Class Names

```html
<div class="{{ error ? 'text-red-600' : 'text-green-600' }}">
  Content
</div>
```

### ❌ Don't Build Classes from Props

```jsx
function Button({ color, children }) {
  return <button className={`bg-${color}-600 hover:bg-${color}-500`}>{children}</button>;
}
```

### ✅ Map Props to Static Classes

```jsx
function Button({ color, children }) {
  const colorVariants = {
    blue: "bg-blue-600 hover:bg-blue-500",
    red: "bg-red-600 hover:bg-red-500",
  };

  return <button className={`${colorVariants[color]} ...`}>{children}</button>;
}
```

## Which Files Are Scanned

Tailwind scans every file in your project except:

- Files in `.gitignore`
- Files in `node_modules`
- Binary files (images, videos, zip files)
- CSS files
- Common package manager lock files

## Explicitly Registering Sources

Use `@source` to explicitly register source paths:

```css
@import "tailwindcss";
@source "../node_modules/@acmecorp/ui-lib";
```

This is useful for external libraries built with Tailwind that are in `.gitignore`.

## Setting Base Path

Set the base path for source detection:

```css
@import "tailwindcss" source("../src");
```

Useful in monorepos where build commands run from the root.

## Ignoring Specific Paths

Use `@source not` to ignore paths:

```css
@import "tailwindcss";
@source not "../src/components/legacy";
```

## Disabling Automatic Detection

Use `source(none)` to disable automatic detection:

```css
@import "tailwindcss" source(none);

@source "../admin";
@source "../shared";
```

Useful for projects with multiple Tailwind stylesheets.

## Safelisting Utilities

Force Tailwind to generate specific classes with `@source inline()`:

```css
@import "tailwindcss";
@source inline("underline");
```

### Safelisting with Variants

Generate classes with variants:

```css
@import "tailwindcss";
@source inline("{hover:,focus:,}underline");
```

### Safelisting with Ranges

Use brace expansion to generate multiple classes:

```css
@import "tailwindcss";
@source inline("{hover:,}bg-red-{50,{100..900..100},950}");
```

This generates `bg-red-50` through `bg-red-950` with hover variants.

## Explicitly Excluding Classes

Use `@source not inline()` to prevent specific classes from being generated:

```css
@import "tailwindcss";
@source not inline("{hover:,focus:,}bg-red-{50,{100..900..100},950}");
```

## Key Points

- Tailwind scans files as plain text
- Always use complete class names, never construct them dynamically
- Map props/state to static class names
- Use `@source` to explicitly register or ignore paths
- Use `@source inline()` to safelist utilities
- Brace expansion works in inline sources for ranges

<!--
Source references:
- https://tailwindcss.com/docs/detecting-classes-in-source-files
-->
