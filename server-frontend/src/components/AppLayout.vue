<script setup>
import { computed, onMounted } from "vue";
import { useRoute } from "vue-router";

import AppLogoIcon from "./AppLogoIcon.vue";
import NavbarSearch from "./NavbarSearch.vue";
import { fetchPricingSettings, usePricingSettings } from "../composables/pricingSettings";
import { useSetGalleryFilter } from "../composables/setGalleryFilter";
import { collectionNavQuery, setScopeQueryFromRoute } from "../utils/setScope";
import { APP_TITLE } from "../constants/app";

const route = useRoute();
const { setPickerMode } = usePricingSettings();
const { setGalleryFilter } = useSetGalleryFilter();

const collectionSubnav = [
  { to: "/collection/all", label: "All cards" },
  { to: "/collection/top", label: "Top owned" },
  { to: "/collection/search", label: "Search" },
  { to: "/stats", label: "Stats" },
];

const navItems = [
  {
    to: "/collection/all",
    label: "Collection",
    matchPrefix: "/collection",
    subnav: collectionSubnav,
  },
  { to: "/storage", label: "Storage", matchPrefix: false },
  { to: "/manager", label: "Set Manager", matchPrefix: false },
  { to: "/decks", label: "Decks", matchPrefix: false },
  { to: "/settings", label: "Settings", matchPrefix: false },
];

const showCollectionSubnav = computed(() =>
  route.path.startsWith("/collection") || route.path === "/stats",
);

const showSetGalleryFilter = computed(
  () => showCollectionSubnav.value && setPickerMode.value === "browser",
);

const showNavbarSearch = computed(() => route.path !== "/collection/search");

const brandLink = computed(() => ({
  path: "/collection/all",
  query: collectionNavQuery(route, "/collection/all"),
}));

function isNavActive(item) {
  if (item.matchPrefix === "/collection") {
    return route.path.startsWith(item.matchPrefix) || route.path === "/stats";
  }
  if (item.matchPrefix) {
    return route.path.startsWith(item.matchPrefix);
  }
  return route.path === item.to;
}

function isSubnavActive(item) {
  return route.path === item.to;
}

function navLinkTo(item) {
  const query = item.matchPrefix === "/collection"
    ? collectionNavQuery(route, item.to)
    : setScopeQueryFromRoute(route);
  if (item.matchPrefix === "/collection") {
    return { path: item.to, query };
  }
  return item.to;
}

function subnavLinkTo(subItem) {
  if (subItem.to === "/stats") {
    return {
      path: "/stats",
      query: setScopeQueryFromRoute(route),
    };
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

        <NavbarSearch v-if="showNavbarSearch" class="app-topbar-search" />
      </header>

      <nav
        v-if="showCollectionSubnav"
        class="app-subnav"
        aria-label="Collection views"
      >
        <template v-for="(subItem, index) in collectionSubnav" :key="subItem.to">
          <RouterLink
            :to="subnavLinkTo(subItem)"
            class="app-subnav-link"
            :class="{ 'is-active': isSubnavActive(subItem) }"
          >
            {{ subItem.label }}
          </RouterLink>
          <label
            v-if="index === 0 && showSetGalleryFilter"
            class="app-subnav-set-filter"
          >
            <span class="sr-only">Filter sets</span>
            <input
              v-model="setGalleryFilter"
              type="search"
              placeholder="Filter sets"
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
  </div>
</template>
