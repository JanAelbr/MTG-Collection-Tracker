import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { VitePWA } from "vite-plugin-pwa";

const APP_NAME = "MTG - Collection tracker";
const APP_SHORT_NAME = "MTG Collection";
const THEME_COLOR = "#1a1f2e";

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: [
        "app-logo.svg",
        "favicon.ico",
        "pwa-64x64.png",
        "pwa-192x192.png",
        "pwa-512x512.png",
        "maskable-icon-512x512.png",
        "apple-touch-icon-180x180.png",
      ],
      manifest: {
        name: APP_NAME,
        short_name: APP_SHORT_NAME,
        description:
          "Track your Magic: The Gathering collection, decks, storage locations, and Cardmarket prices.",
        theme_color: THEME_COLOR,
        background_color: THEME_COLOR,
        display: "standalone",
        scope: "/",
        start_url: "/",
        orientation: "any",
        icons: [
          {
            src: "pwa-64x64.png",
            sizes: "64x64",
            type: "image/png",
          },
          {
            src: "pwa-192x192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "pwa-512x512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "maskable-icon-512x512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2}"],
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api/, /^\/docs/, /^\/redoc/, /openapi\.json/],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/cdn\.jsdelivr\.net\/gh\/Investigamer\/mtg-vectors@/i,
            handler: "CacheFirst",
            options: {
              cacheName: "mtg-vectors-set-icons",
              expiration: {
                maxEntries: 600,
                maxAgeSeconds: 60 * 60 * 24 * 365,
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },
          {
            urlPattern: /^https:\/\/svgs\.scryfall\.io\/sets\//i,
            handler: "CacheFirst",
            options: {
              cacheName: "scryfall-set-icons",
              expiration: {
                maxEntries: 400,
                maxAgeSeconds: 60 * 60 * 24 * 365,
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },
          {
            urlPattern: /^https:\/\/svgs\.scryfall\.io\/card-symbols\//i,
            handler: "CacheFirst",
            options: {
              cacheName: "scryfall-card-symbols",
              expiration: {
                maxEntries: 120,
                maxAgeSeconds: 60 * 60 * 24 * 365,
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },
        ],
      },
      devOptions: {
        enabled: true,
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/docs": "http://127.0.0.1:8000",
      "/redoc": "http://127.0.0.1:8000",
      "/openapi.json": "http://127.0.0.1:8000",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
