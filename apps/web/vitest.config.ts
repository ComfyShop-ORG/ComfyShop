import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// 组件交互测试在 jsdom 中运行。纯函数的 `*.test.ts` 由根目录的 node:test 运行。
export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom', include: ['src/**/*.test.tsx'], restoreMocks: true },
});
