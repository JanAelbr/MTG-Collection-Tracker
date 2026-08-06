<script setup>
import { computed, onMounted } from "vue";
import { useRoute } from "vue-router";

import AppLogoIcon from "./AppLogoIcon.vue";
import NavbarSearch from "./NavbarSearch.vue";
import ConfirmDialogHost from "./ConfirmDialogHost.vue";
import { fetchPricingSettings } from "../composables/pricingSettings";
import { useDeckGalleryFilter } from "../composables/deckGalleryFilter";
import { useSetGalleryFilter } from "../composables/setGalleryFilter";
import { collectionNavQuery, setScopeQueryFromRoute } from "../utils/setScope";
import { APP_TITLE } from "../constants/app";

const route = useRoute();
const { setGalleryFilter } = useSetGalleryFilter();
const { deckGalleryFilter } = useDeckGalleryFilter();

const collectionSubnav = [
  { to: "/collection/all", label: "Catalog" },
  { to: "/storage", label: "Storage" },
  { to: "/collection/decks", label: "Decks" },
];

const printSubnav = [
  { to: "/print/cards", label: "Cards" },
  { to: "/print/separators", label: "Separators" },
];

const settingsSubnav = [
  { to: "/settings/display", label: "Display" },
  { to: "/settings/sets", label: "Sets" },
  { to: "/settings/stats", label: "Stats" },
  { to: "/settings/sync", label: "Sync" },
  { to: "/settings/backup", label: "Backup" },
];

const navItems = [
  { to: "/", label: "Favourites", matchPrefix: false },
  {
    to: "/collection/all",
    label: "Collection",
    matchPrefix: "/collection",
    subnav: collectionSubnav,
  },
  {
    to: "/print/cards",
    label: "Print",
    matchPrefix: "/print",
    subnav: printSubnav,
  },
  { to: "/sell", label: "Sell", matchPrefix: false },
  {
    to: "/settings/display",
    label: "Settings",
    matchPrefix: "/settings",
    subnav: settingsSubnav,
  },
];

const showCollectionSubnav = computed(() =>
  route.path.startsWith("/collection") || route.path === "/storage",
);

const showPrintSubnav = computed(() => route.path.startsWith("/print"));

const showSettingsSubnav = computed(() => route.path.startsWith("/settings"));

const activeSubnav = computed(() => {
  if (showCollectionSubnav.value) {
    return { items: collectionSubnav, label: "Collection views" };
  }
  if (showPrintSubnav.value) {
    return { items: printSubnav, label: "Print views" };
  }
  if (showSettingsSubnav.value) {
    return { items: settingsSubnav, label: "Settings views" };
  }
  return null;
});

const showSetGalleryFilter = computed(() =>
  route.path === "/collection/all" || route.path.startsWith("/collection/search"),
);

const showDeckGalleryFilter = computed(() => route.path.startsWith("/collection/decks"));

const showNavbarSearch = computed(() => route.path !== "/collection/search");

const isAdvancedSearchActive = computed(() => route.path === "/collection/search");

const advancedSearchLink = computed(() => ({
  path: "/collection/search",
  query: collectionNavQuery(route, "/collection/search"),
}));

const brandLink = computed(() => ({
  path: "/",
}));

function isNavActive(item) {
  if (item.to === "/") {
    return route.path === "/";
  }
  if (item.matchPrefix === "/collection") {
    return (
      route.path.startsWith(item.matchPrefix)
      || route.path === "/storage"
    );
  }
  if (item.matchPrefix) {
    return route.path.startsWith(item.matchPrefix);
  }
  return route.path === item.to;
}

function isSubnavActive(item) {
  if (item.to === "/collection/decks") {
    return route.path.startsWith("/collection/decks");
  }
  return route.path === item.to;
}

function navLinkTo(item) {
  if (item.to === "/") {
    return "/";
  }
  const query = item.matchPrefix === "/collection"
    ? collectionNavQuery(route, item.to)
    : setScopeQueryFromRoute(route);
  if (item.matchPrefix === "/collection") {
    return { path: item.to, query };
  }
  return item.to;
}

function subnavLinkTo(subItem) {
  if (
    subItem.to.startsWith("/print/")
    || subItem.to.startsWith("/settings/")
    || subItem.to === "/storage"
    || subItem.to === "/collection/decks"
  ) {
    return subItem.to;
  }
  return {
    path: subItem.to,
    query: collectionNavQuery(route, subItem.to),
  };
}

onMounted(() => {
  fetchPricingSettings();
});
</script>

<template>
  <div class="app-shell">
    <div class="app-chrome">
      <header class="app-topbar">
        <div class="app-topbar-main">
          <RouterLink :to="brandLink" class="app-brand" aria-label="Home">
            <AppLogoIcon class="app-brand-icon" :size="22" />
            <span class="app-brand-text">{{ APP_TITLE }}</span>
          </RouterLink>

          <nav class="app-topnav" aria-label="Main navigation">
            <RouterLink
              v-for="item in navItems"
              :key="item.to"
              :to="navLinkTo(item)"
              class="app-topnav-link"
              :class="{ 'is-active': isNavActive(item) }"
            >
              {{ item.label }}
            </RouterLink>
          </nav>
        </div>

        <div class="app-topbar-search-cluster">
          <NavbarSearch v-if="showNavbarSearch" class="app-topbar-search" />
          <RouterLink
            :to="advancedSearchLink"
            class="app-topbar-advanced-search"
            :class="{ 'is-active': isAdvancedSearchActive }"
          >
            Advanced search
          </RouterLink>
        </div>
      </header>

      <nav
        v-if="activeSubnav"
        class="app-subnav"
        :aria-label="activeSubnav.label"
      >
        <template v-for="subItem in activeSubnav.items" :key="subItem.to">
          <RouterLink
            :to="subnavLinkTo(subItem)"
            class="app-subnav-link"
            :class="{ 'is-active': isSubnavActive(subItem) }"
          >
            {{ subItem.label }}
          </RouterLink>
          <label
            v-if="subItem.to === '/collection/all' && showSetGalleryFilter"
            class="app-subnav-set-filter"
          >
            <span class="sr-only">Search sets</span>
            <input
              v-model="setGalleryFilter"
              type="search"
              placeholder="Search sets"
              autocomplete="off"
              spellcheck="false"
            />
          </label>
          <label
            v-else-if="subItem.to === '/collection/decks' && showDeckGalleryFilter"
            class="app-subnav-set-filter"
          >
            <span class="sr-only">Search decks</span>
            <input
              v-model="deckGalleryFilter"
              type="search"
              placeholder="Search decks"
              autocomplete="off"
              spellcheck="false"
            />
          </label>
        </template>
      </nav>
    </div>

    <main class="app-main">
      <slot />
    </main>
    <ConfirmDialogHost />
  </div>
</template>
