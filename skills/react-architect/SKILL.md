---
name: react-architect
description: Build production-grade React applications with modern architecture, state management, and performance optimization. Use when: (1) creating new React projects, (2) component architecture design, (3) state management setup (Redux, Zustand, Jotai), (4) React Router configuration, (5) custom hooks development, (6) performance optimization (React.memo, useMemo, useCallback), (7) code splitting and lazy loading, (8) testing setup. Supports React 18+, Next.js, Vite. Triggers: "React project", "create component", "state management", "React hooks", "Next.js", "Redux", "component architecture".
---

# React Architect

Modern React application architecture and best practices.

## Project Setup

### Vite (Recommended)

```bash
# Create new project
npm create vite@latest my-app -- --template react-ts
cd my-app
npm install

# Add common dependencies
npm install react-router-dom zustand axios
npm install -D @types/react @types/react-dom
```

### Next.js (Full-stack)

```bash
# Create Next.js app
npx create-next-app@latest my-app --typescript --tailwind --app

# Project structure
my-app/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   └── api/
├── components/
├── lib/
└── public/
```

## Component Architecture

### File Structure

```
src/
├── components/
│   ├── ui/              # Reusable UI components
│   │   ├── Button/
│   │   │   ├── Button.tsx
│   │   │   ├── Button.test.tsx
│   │   │   └── index.ts
│   │   └── Input/
│   ├── features/        # Feature-specific components
│   │   └── auth/
│   │       ├── LoginForm.tsx
│   │       └── RegisterForm.tsx
│   └── layouts/         # Layout components
│       └── MainLayout.tsx
├── hooks/               # Custom hooks
├── lib/                 # Utilities and configs
├── types/               # TypeScript types
└── pages/               # Page components (if not using Next.js)
```

### Component Template

```tsx
// components/ui/Button/Button.tsx
import { forwardRef, ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', isLoading, children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          'rounded font-medium transition-colors',
          variants[variant],
          sizes[size],
          disabled && 'opacity-50 cursor-not-allowed',
          className
        )}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading ? <Spinner /> : children}
      </button>
    );
  }
);

const variants = {
  primary: 'bg-blue-600 text-white hover:bg-blue-700',
  secondary: 'bg-gray-200 text-gray-900 hover:bg-gray-300',
  danger: 'bg-red-600 text-white hover:bg-red-700'
};

const sizes = {
  sm: 'px-3 py-1 text-sm',
  md: 'px-4 py-2',
  lg: 'px-6 py-3 text-lg'
};
```

## State Management

### Zustand (Recommended)

```tsx
// stores/useAuthStore.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      login: async (email, password) => {
        const { user, token } = await authApi.login(email, password);
        set({ user, token });
      },
      logout: () => set({ user: null, token: null })
    }),
    { name: 'auth-storage' }
  )
);

// Usage
function Profile() {
  const { user, logout } = useAuthStore();
  return <div>{user?.name} <button onClick={logout}>Logout</button></div>;
}
```

### Redux Toolkit

```tsx
// store/userSlice.ts
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

export const fetchUser = createAsyncThunk('user/fetch', async (id: string) => {
  return await userApi.fetch(id);
});

const userSlice = createSlice({
  name: 'user',
  initialState: { data: null, loading: false },
  reducers: {
    clearUser: (state) => { state.data = null; }
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchUser.pending, (state) => { state.loading = true; })
      .addCase(fetchUser.fulfilled, (state, action) => {
        state.loading = false;
        state.data = action.payload;
      });
  }
});
```

## Custom Hooks

```tsx
// hooks/useLocalStorage.ts
export function useLocalStorage<T>(key: string, initialValue: T) {
  const [value, setValue] = useState<T>(() => {
    const stored = localStorage.getItem(key);
    return stored ? JSON.parse(stored) : initialValue;
  });

  useEffect(() => {
    localStorage.setItem(key, JSON.stringify(value));
  }, [key, value]);

  return [value, setValue] as const;
}

// hooks/useFetch.ts
export function useFetch<T>(url: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(url)
      .then(res => res.json())
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [url]);

  return { data, error, loading };
}
```

## Performance Optimization

### Code Splitting

```tsx
// Lazy load components
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Settings = lazy(() => import('./pages/Settings'));

function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Suspense>
  );
}
```

### Memoization

```tsx
// Memoize expensive components
const ExpensiveList = memo(function ExpensiveList({ items }: Props) {
  return items.map(item => <Item key={item.id} {...item} />);
});

// Memoize computations
function DataTable({ data, filter }: Props) {
  const filteredData = useMemo(
    () => data.filter(item => item.name.includes(filter)),
    [data, filter]
  );
  
  return <Table data={filteredData} />;
}

// Memoize callbacks
function Parent() {
  const [count, setCount] = useState(0);
  const handleClick = useCallback(() => setCount(c => c + 1), []);
  return <Child onClick={handleClick} />;
}
```

## React Router

```tsx
// router/index.tsx
import { createBrowserRouter, RouterProvider } from 'react-router-dom';

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Home /> },
      { path: 'dashboard', element: <Dashboard /> },
      { 
        path: 'admin',
        element: <ProtectedRoute role="admin" />,
        children: [
          { path: 'users', element: <UserManagement /> }
        ]
      }
    ]
  }
]);

function App() {
  return <RouterProvider router={router} />;
}
```

## Scripts

- `scripts/create_component.sh` - Generate component with tests
- `scripts/setup_tailwind.sh` - Configure Tailwind CSS
- `scripts/analyze_bundle.sh` - Analyze bundle size

## References

- `references/project_templates/` - Starter templates (Vite, Next.js)
- `references/testing_patterns.md` - React Testing Library patterns
- `references/ssr_patterns.md` - Server-side rendering guide

## Assets

- `assets/component_template/` - Reusable component boilerplate
- `assets/hook_template/` - Custom hook boilerplate
