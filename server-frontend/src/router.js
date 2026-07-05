import { createRouter, createWebHistory } from "vue-router";
import { APP_TITLE } from "./constants/app";
import StorageView from "./views/StorageView.vue";
import ManagerView from "./views/ManagerView.vue";
import CollectionView from "./views/CollectionView.vue";
import CollectionSearchView from "./views/CollectionSearchView.vue";
import StatsView from "./views/StatsView.vue";
import DecksView from "./views/DecksView.vue";
import CardDetailView from "./views/CardDetailView.vue";
import HomeView from "./views/HomeView.vue";

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
    { path: "/", redirect: "/collection/all" },
    { path: "/collection", redirect: "/collection/all" },
    {
      path: "/collection/search",
      name: "collection-search",
      component: CollectionSearchView,
      meta: { title: "Collection" },
    },
    {
      path: "/collection/:view(top|all)",
      name: "collection",
      component: CollectionView,
      meta: { title: "Collection" },
    },
    { path: "/collection/risers", redirect: "/collection/all" },
    { path: "/collection/fallers", redirect: "/collection/all" },
    { path: "/reports", redirect: "/collection/all" },
    {
      path: "/reports/:view(top|all)",
      redirect: (to) => `/collection/${to.params.view}`,
    },
    { path: "/reports/risers", redirect: "/collection/all" },
    { path: "/reports/fallers", redirect: "/collection/all" },
    {
      path: "/settings",
      name: "settings",
      component: HomeView,
      meta: { title: "Settings" },
    },
    { path: "/home", redirect: "/settings" },
    {
      path: "/storage",
      name: "storage",
      component: StorageView,
      meta: { title: "Storage" },
    },
    {
      path: "/manager",
      name: "manager",
      component: ManagerView,
      meta: { title: "Set Manager" },
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
