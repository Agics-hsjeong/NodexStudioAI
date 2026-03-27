import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  envPrefix: ['VITE_', 'PUBLIC_'],
  plugins: [svelte()],
  server: {
    host: true,
    port: 3000,
    // nginx 프록시로 커스텀 Host 허용 (www 도메인)
    allowedHosts: true
  }
});

