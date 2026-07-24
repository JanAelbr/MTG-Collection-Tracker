<script setup>
import { computed, onMounted } from "vue";
import { useRoute } from "vue-router";

import AppLogoIcon from "./AppLogoIcon.vue";
import NavbarSearch from "./NavbarSearch.vue";
import { fetchPricingSettings } from "../composables/pricingSettings";
import { useSetGalleryFilter } from "../composables/setGalleryFilter";
import { collectionNavQuery, setScopeQueryFromRoute } from "../utils/setScope";
import { APP_TITLE } from "../constants/app";

const route = useRoute();
const { setGalleryFilter } = useSetGalleryFilter();

const collectionSubnav = [
  { to: "/collection/all", label: "All cards" },
  { to: "/stats", label: "Stats" },
];

const navItems = [
  { to: "/", label: "Favourites", matchPrefix: false },
  {
    to: "/collection/all",
    label: "Collection",
    matchPrefix: "/collection",
    subnav: collectionSubnav,
  },
  { to: "/storage", label: "Storage", matchPrefix: false },
  { to: "/scan", label: "Scan", matchPrefix: false },
  { to: "/decks", label: "Decks", matchPrefix: false },
  { to: "/settings", label: "Settings", matchPrefix: false },
];

const showCollectionSubnav = computed(() =>
  route.path.startsWith("/collection") || route.path === "/stats",
);

const showSetGalleryFilter = computed(() => showCollectionSubnav.value);

const showNavbarSearch = computed(() =>
  route.path !== "/collection/search" && route.path !== "/scan",
);

const showAdvancedSearchLink = computed(() => route.path !== "/scan");

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

        <div v-if="showNavbarSearch || showAdvancedSearchLink" class="app-topbar-search-cluster">
          <NavbarSearch v-if="showNavbarSearch" class="app-topbar-search" />
          <RouterLink
            v-if="showAdvancedSearchLink"
            :to="advancedSearchLink"
            class="app-topbar-advanced-search"
            :class="{ 'is-active': isAdvancedSearchActive }"
          >
            Advanced search
          </RouterLink>
        </div>
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
            <span class="sr-only">Search sets</span>
            <input
              v-model="setGalleryFilter"
              type="search"
              placeholder="Search sets"
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
