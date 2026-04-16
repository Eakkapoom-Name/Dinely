import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path';

// https://vite.dev/config/
export default defineConfig({
    plugins: [vue()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    server: { // dev
        host: '0.0.0.0', // Allows Vite to listen on all interfaces
        port: 8080, // Ensure the port matches the one in your Dockerfile
        proxy: {
            '/api': {
                target: 'http://fastapi:8080',
                changeOrigin: true,
            }
        }
    },
})
