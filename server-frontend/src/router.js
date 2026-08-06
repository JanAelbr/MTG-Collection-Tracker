import { createRouter, createWebHistory } from "vue-router";
import { APP_TITLE } from "./constants/app";

// Route components are lazy-loaded so the initial bundle only pays for the
// view the user actually lands on.
const StorageView = () => import("./views/StorageView.vue");
const SellView = () => import("./views/SellView.vue");
const CollectionView = () => import("./views/CollectionView.vue");
const CollectionSearchView = () => import("./views/CollectionSearchView.vue");
const DecksView = () => import("./views/DecksView.vue");
const DeckBuilderView = () => import("./views/DeckBuilderView.vue");
const CardDetailView = () => import("./views/CardDetailView.vue");
const FavoritesHomeView = () => import("./views/FavoritesHomeView.vue");
const SettingsDisplayView = () => import("./views/SettingsDisplayView.vue");
const SettingsStatsView = () => import("./views/SettingsStatsView.vue");
const SettingsSyncView = () => import("./views/SettingsSyncView.vue");
const SettingsBackupView = () => import("./views/SettingsBackupView.vue");
const SetsView = () => import("./views/SetsView.vue");
const PrintCardsView = () => import("./views/PrintCardsView.vue");
const SeparatorsView = () => import("./views/SeparatorsView.vue");

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
    { path: "/collection/roles", redirect: "/collection/search" },
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
    { path: "/settings", redirect: "/settings/display" },
    {
      path: "/settings/display",
      name: "settings-display",
      component: SettingsDisplayView,
      meta: { title: "Settings" },
    },
    {
      path: "/settings/sets",
      name: "settings-sets",
      component: SetsView,
      meta: { title: "Sets" },
    },
    {
      path: "/settings/stats",
      name: "settings-stats",
      component: SettingsStatsView,
      meta: { title: "Stats" },
    },
    {
      path: "/settings/sync",
      name: "settings-sync",
      component: SettingsSyncView,
      meta: { title: "Settings" },
    },
    {
      path: "/settings/backup",
      name: "settings-backup",
      component: SettingsBackupView,
      meta: { title: "Settings" },
    },
    { path: "/home", redirect: "/" },
    { path: "/sets", redirect: "/settings/sets" },
    {
      path: "/storage",
      name: "storage",
      component: StorageView,
      meta: { title: "Storage" },
    },
    { path: "/print", redirect: "/print/cards" },
    {
      path: "/print/cards",
      name: "print-cards",
      component: PrintCardsView,
      meta: { title: "Print Cards" },
    },
    {
      path: "/print/separators",
      name: "print-separators",
      component: SeparatorsView,
      meta: { title: "Separators" },
    },
    { path: "/separators", redirect: "/print/separators" },
    {
      path: "/sell",
      name: "sell",
      component: SellView,
      meta: { title: "Sell" },
    },
    { path: "/scan", redirect: "/" },
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
      redirect: (to) => {
        const set = typeof to.query.set === "string" ? to.query.set : "";
        if (set && set.toLowerCase() !== "all") {
          return {
            path: "/collection/all",
            query: {
              set,
              ...(to.query.family != null ? { family: to.query.family } : {}),
              view: "stats",
            },
          };
        }
        return "/settings/stats";
      },
    },
    { path: "/decks/browse", redirect: "/collection/decks" },
    { path: "/decks/stats", redirect: "/collection/decks" },
    {
      path: "/decks",
      redirect: (to) => ({ path: "/collection/decks", query: to.query }),
    },
    {
      path: "/decks/build",
      name: "deck-builder",
      component: DeckBuilderView,
      meta: { title: "Deck Builder" },
    },
    {
      path: "/collection/decks/build",
      redirect: (to) => ({
        path: "/decks/build",
        query: to.query,
      }),
    },
    {
      path: "/collection/decks",
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
