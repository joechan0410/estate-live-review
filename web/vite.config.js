import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  server: { host: 'localhost' },
  preview: { host: 'localhost' },
  build: { target: 'es2022' },
});
