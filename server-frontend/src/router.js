import { createRouter, createWebHistory } from "vue-router";
import { APP_TITLE } from "./constants/app";
import StorageView from "./views/StorageView.vue";
import CollectionView from "./views/CollectionView.vue";
import CollectionSearchView from "./views/CollectionSearchView.vue";
import StatsView from "./views/StatsView.vue";
import DecksView from "./views/DecksView.vue";
import DeckBuilderView from "./views/DeckBuilderView.vue";
import CardDetailView from "./views/CardDetailView.vue";
import HomeView from "./views/HomeView.vue";
import FavoritesHomeView from "./views/FavoritesHomeView.vue";
import ScanView from "./views/ScanView.vue";

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
