---
name: core-installation
description: Installing Tailwind CSS with Vite, PostCSS, CLI, or CDN
---

# Installation

How to add Tailwind CSS to a project.

## Vite (Recommended)

```bash
npm install tailwindcss @tailwindcss/vite
```

```ts
// vite.config.ts
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [tailwindcss()],
})
```

```css
/* style.css */
@import "tailwindcss";
```

## PostCSS

```bash
npm install tailwindcss @tailwindcss/postcss postcss
```

```js
// postcss.config.js
export default {
  plugins: {
    '@tailwindcss/postcss': {},
  },
}
```

```css
@import "tailwindcss";
```

## Tailwind CLI

```bash
npx @tailwindcss/cli -i ./src/input.css -o ./dist/output.css --watch
```

```css
/* input.css */
@import "tailwindcss";
```

## Play CDN (Development only)

```html
<script src="https://cdn.tailwindcss.com"></script>
```

Not for production: no purging, larger payload.

## Framework guides

- **Nuxt**: `@nuxtjs/tailwindcss` module or `@tailwindcss/vite`
- **Next.js**: Use Vite or PostCSS with `tailwind.config.js` if needed
- **React Router / SvelteKit / SolidJS**: Use `@tailwindcss/vite`

## Key Points

- Vite: `@tailwindcss/vite` plugin + `@import "tailwindcss"`
- PostCSS: `@tailwindcss/postcss`
- CLI: `npx @tailwindcss/cli`
- v4 uses CSS-first config; no `tailwind.config.js` required for basics
- Use `@theme` in CSS to customize design tokens

<!--
Source references:
- https://tailwindcss.com/docs/installation/using-vite
- https://tailwindcss.com/docs/installation/using-postcss
- https://tailwindcss.com/docs/installation/tailwind-cli
- https://tailwindcss.com/docs/installation/play-cdn
-->
