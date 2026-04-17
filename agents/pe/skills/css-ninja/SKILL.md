---
name: css-ninja
description: Master CSS with Tailwind, CSS-in-JS, responsive layouts, animations, and modern styling patterns. Use when: (1) responsive design implementation, (2) Tailwind CSS setup and customization, (3) CSS-in-JS (styled-components, emotion), (4) complex layouts (Grid, Flexbox), (5) CSS animations and transitions, (6) dark mode implementation, (7) component styling systems, (8) CSS architecture (BEM, utility-first). Triggers: "responsive", "Tailwind", "styled-components", "CSS grid", "flexbox", "animation", "dark mode", "layout".
---

# CSS Ninja

Modern CSS mastery with Tailwind, CSS-in-JS, and responsive design patterns.

## Tailwind CSS

### Setup

```bash
# Install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p

# Configure
# tailwind.config.js
export default {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f9ff',
          500: '#3b82f6',
          900: '#1e3a8a'
        }
      }
    }
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography')
  ]
}
```

### Responsive Design

```html
<!-- Mobile-first responsive patterns -->
<div class="
  p-4           /* base: mobile */
  md:p-6        /* tablet+ */
  lg:p-8        /* desktop+ */
  xl:max-w-7xl  /* large desktop */
">
  <!-- Grid responsive -->
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    <Card />
    <Card />
    <Card />
  </div>
  
  <!-- Flex responsive -->
  <nav class="flex flex-col md:flex-row md:justify-between">
    <Logo />
    <Menu />
  </nav>
  
  <!-- Hide/show responsive -->
  <div class="hidden md:block">Desktop only</div>
  <div class="md:hidden">Mobile only</div>
</div>
```

### Common Patterns

```html
<!-- Centered container -->
<div class="flex items-center justify-center min-h-screen">
  <Card />
</div>

<!-- Sticky header -->
<header class="sticky top-0 z-50 bg-white/80 backdrop-blur-md">
  <Nav />
</header>

<!-- Card hover effect -->
<div class="
  transition-all duration-300 
  hover:shadow-xl hover:-translate-y-1
  hover:ring-2 hover:ring-blue-500
">
  <CardContent />
</div>

<!-- Gradient text -->
<h1 class="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
  Gradient Heading
</h1>

<!-- Aspect ratio -->
<div class="aspect-video w-full">
  <img class="w-full h-full object-cover" />
</div>
```

## CSS-in-JS

### Styled Components

```tsx
import styled from 'styled-components';

const Button = styled.button<{ $variant?: 'primary' | 'secondary' }>`
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  font-weight: 500;
  transition: all 0.2s;
  
  ${props => props.$variant === 'primary' && `
    background: #3b82f6;
    color: white;
    &:hover { background: #2563eb; }
  `}
  
  ${props => props.$variant === 'secondary' && `
    background: transparent;
    border: 1px solid #3b82f6;
    color: #3b82f6;
    &:hover { background: #eff6ff; }
  `}
`;

// Usage
<Button $variant="primary">Click me</Button>
```

### Emotion

```tsx
/** @jsxImportSource @emotion/react */
import { css } from '@emotion/react';

const buttonStyles = css`
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
`;

function Button({ children }) {
  return <button css={buttonStyles}>{children}</button>;
}
```

## Layouts

### Flexbox Patterns

```css
/* Center everything */
.center { display: flex; align-items: center; justify-content: center; }

/* Space between */
.header { display: flex; justify-content: space-between; align-items: center; }

/* Equal spacing */
.nav { display: flex; gap: 1rem; }

/* Sticky footer */
.page { display: flex; flex-direction: column; min-height: 100vh; }
.content { flex: 1; }
```

### Grid Patterns

```css
/* Auto-fit responsive grid */
.grid-auto {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
}

/* Holy grail layout */
.layout {
  display: grid;
  grid-template-areas:
    "header header"
    "sidebar main"
    "footer footer";
  grid-template-columns: 250px 1fr;
  grid-template-rows: auto 1fr auto;
  min-height: 100vh;
}

.header { grid-area: header; }
.sidebar { grid-area: sidebar; }
.main { grid-area: main; }
.footer { grid-area: footer; }
```

## Animations

### Tailwind Animations

```html
<!-- Fade in -->
<div class="animate-fade-in">
  Content fades in
</div>

<!-- Pulse -->
<div class="animate-pulse">Loading...</div>

<!-- Spin -->
<svg class="animate-spin h-5 w-5">...</svg>

<!-- Bounce -->
<div class="animate-bounce">↓</div>
```

### Custom Animations

```css
/* tailwind.config.js */
module.exports = {
  theme: {
    extend: {
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in',
        'slide-up': 'slideUp 0.3s ease-out',
        'scale-in': 'scaleIn 0.2s ease'
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' }
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' }
        },
        scaleIn: {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' }
        }
      }
    }
  }
}
```

## Dark Mode

```tsx
// tailwind.config.js
module.exports = {
  darkMode: 'class', // or 'media'
  // ...
}

// Toggle implementation
function ThemeToggle() {
  const [dark, setDark] = useState(() => 
    localStorage.theme === 'dark'
  );
  
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    localStorage.theme = dark ? 'dark' : 'light';
  }, [dark]);
  
  return (
    <button onClick={() => setDark(!dark)}>
      {dark ? '☀️' : '🌙'}
    </button>
  );
}
```

```html
<!-- Usage -->
<div class="bg-white dark:bg-gray-900">
  <h1 class="text-gray-900 dark:text-white">Hello</h1>
</div>
```

## Responsive Breakpoints

```css
/* Standard breakpoints */
/* sm: 640px */
/* md: 768px */
/* lg: 1024px */
/* xl: 1280px */
/* 2xl: 1536px */

/* Tailwind usage */
<div class="
  text-sm      /* base */
  md:text-base /* tablet+ */
  lg:text-lg   /* desktop+ */
">
```

## References

- `references/tailwind_cheatsheet.md` - Complete Tailwind reference
- `references/css_patterns.md` - Common CSS layout patterns
- `references/animation_library.md` - Framer Motion / GSAP patterns
