import { gzipSync } from 'node:zlib';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'comfyshop-precompress-scripts',
      apply: 'build',
      generateBundle: {
        order: 'post',
        handler(_options, bundle) {
          for (const chunk of Object.values(bundle)) {
            if (chunk.type !== 'chunk') continue;
            const compressed = gzipSync(chunk.code, { level: 9 });
            if (compressed.length < Buffer.byteLength(chunk.code)) {
              this.emitFile({
                type: 'asset',
                fileName: chunk.fileName + '.gz',
                source: compressed,
              });
            }
          }
        },
      },
    },
  ],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '^/(api|downloads)(/|$)': { target: 'http://127.0.0.1:8688', changeOrigin: false } },
  },
});
