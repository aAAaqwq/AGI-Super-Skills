import { Suspense } from 'react';
import Sandbox from '@/components/Sandbox/Sandbox';

export default function SandboxPage() {
  return (
    <Suspense fallback={<div className="p-8">加载中...</div>}>
      <Sandbox />
    </Suspense>
  );
}
