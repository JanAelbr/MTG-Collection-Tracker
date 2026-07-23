import { createRouter, createWebHistory } from "vue-router";
import { APP_TITLE } from "./constants/app";

// Route components are lazy-loaded so the initial bundle only pays for the
// view the user actually lands on. ScanView pulls in tesseract.js (OCR), by
// far the heaviest dependency, so it benefits the most from code-splitting.
const StorageView = () => import("./views/StorageView.vue");
const CollectionView = () => import("./views/CollectionView.vue");
const CollectionSearchView = () => import("./views/CollectionSearchView.vue");
const StatsView = () => import("./views/StatsView.vue");
const DecksView = () => import("./views/DecksView.vue");
const DeckBuilderView = () => import("./views/DeckBuilderView.vue");
const CardDetailView = () => import("./views/CardDetailView.vue");
const HomeView = () => import("./views/HomeView.vue");
const FavoritesHomeView = () => import("./views/FavoritesHomeView.vue");
const ScanView = () => import("./views/ScanView.vue");

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition;
    }
    if (to.path === from.path && to.name === from.name) {
      return false;
    }
    return { top: 0 };
  },
  routes: [
    { path: "/", name: "home", component: FavoritesHomeView, meta: { title: "Favourites" } },
    { path: "/collection", redirect: "/collection/all" },
    {
      path: "/collection/search",
      name: "collection-search",
      component: CollectionSearchView,
      meta: { title: "Collection" },
    },
    {
      path: "/collection/all",
      name: "collection",
      component: CollectionView,
      meta: { title: "Collection" },
    },
    { path: "/collection/top", redirect: "/collection/all" },
    { path: "/collection/risers", redirect: "/collection/all" },
    { path: "/collection/fallers", redirect: "/collection/all" },
    { path: "/reports", redirect: "/collection/all" },
    {
      path: "/reports/:view(top|all)",
      redirect: "/collection/all",
    },
    { path: "/reports/risers", redirect: "/collection/all" },
    { path: "/reports/fallers", redirect: "/collection/all" },
    {
      path: "/settings",
      name: "settings",
      component: HomeView,
      meta: { title: "Settings" },
    },
    { path: "/home", redirect: "/" },
    {
      path: "/storage",
      name: "storage",
      component: StorageView,
      meta: { title: "Storage" },
    },
    {
      path: "/scan",
      name: "scan",
      component: ScanView,
      meta: { title: "Scan" },
    },
    {
      path: "/manager",
      redirect: (to) => ({
        path: "/collection/all",
        query: {
          ...(typeof to.query.set === "string" ? { set: to.query.set } : {}),
          ...(to.query.editArtStyles != null ? { editArtStyles: to.query.editArtStyles } : {}),
          view: "table",
        },
      }),
    },
    {
      path: "/stats",
      name: "stats",
      component: StatsView,
      meta: { title: "Collection Stats" },
    },
    { path: "/decks/browse", redirect: "/decks" },
    { path: "/decks/stats", redirect: "/decks" },
    {
      path: "/decks/build",
      name: "deck-builder",
      component: DeckBuilderView,
      meta: { title: "Deck Builder" },
    },
    {
      path: "/decks",
      name: "decks",
      component: DecksView,
      meta: { title: "Decks" },
    },
    {
      path: "/card/:setCode/:collectorNumber",
      name: "card",
      component: CardDetailView,
      meta: { title: "Card Detail" },
    },
  ],
});

router.afterEach((to) => {
  const section = typeof to.meta.title === "string" ? to.meta.title : "";
  document.title = section ? `${APP_TITLE} · ${section}` : APP_TITLE;
});

export default router;
