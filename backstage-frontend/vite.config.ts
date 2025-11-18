import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      // 允许读取仓库根目录，方便共享资源
      allow: ['..']
    }
  }
});
