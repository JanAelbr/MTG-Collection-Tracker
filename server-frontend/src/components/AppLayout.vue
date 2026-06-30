<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";

import { collectionNavQuery, setScopeQueryFromRoute } from "../utils/setScope";
import { APP_TITLE } from "../constants/app";

const route = useRoute();

const collectionSubnav = [
  { to: "/collection/all", label: "All cards" },
  { to: "/collection/top", label: "Top owned" },
  { to: "/collection/search", label: "Search" },
];

const navItems = [
  {
    to: "/collection/all",
    label: "Collection",
    matchPrefix: "/collection",
    subnav: collectionSubnav,
  },
  { to: "/stats", label: "Stats", matchPrefix: false },
  { to: "/storage", label: "Storage", matchPrefix: false },
  { to: "/manager", label: "Set Manager", matchPrefix: false },
  { to: "/decks", label: "Decks", matchPrefix: false },
  { to: "/settings", label: "Settings", matchPrefix: false },
];

const pageTitle = computed(() => {
  if (route.path.startsWith("/collection/")) {
    const activeView = collectionSubnav.find((item) => route.path === item.to);
    if (activeView) {
      return `Collection · ${activeView.label}`;
    }
  }
  return route.meta.title || APP_TITLE;
});

function isNavActive(item) {
  if (item.matchPrefix) {
    return route.path.startsWith(item.matchPrefix);
  }
  return route.path === item.to;
}

function isSubnavActive(item) {
  return route.path === item.to;
}

function isSubnavOpen(item) {
  return Boolean(item.matchPrefix && route.path.startsWith(item.matchPrefix));
}

function navLinkTo(item) {
  const query = item.matchPrefix === "/collection"
    ? collectionNavQuery(route, item.to)
    : setScopeQueryFromRoute(route);
  if (item.matchPrefix === "/collection" || item.to === "/stats") {
    return { path: item.to, query };
  }
  return item.to;
}

function subnavLinkTo(item, subItem) {
  return {
    path: subItem.to,
    query: collectionNavQuery(route, subItem.to),
  };
}
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <h1>{{ APP_TITLE }}</h1>
      <p class="app-subtitle">{{ pageTitle }}</p>
    </header>

    <div class="report-layout">
      <aside class="side-nav">
        <nav aria-label="Main navigation" class="side-nav-list">
          <div
            v-for="item in navItems"
            :key="item.to"
            class="side-nav-group"
            :class="{ 'has-subnav': item.subnav }"
          >
            <RouterLink
              :to="navLinkTo(item)"
              class="side-nav-link"
              :class="{ 'is-active': isNavActive(item) && !item.subnav }"
            >
              {{ item.label }}
            </RouterLink>

            <div
              v-if="item.subnav"
              class="side-nav-sub-wrap"
              :class="{ 'is-open': isSubnavOpen(item) }"
            >
              <div class="side-nav-sub-inner">
                <div class="side-nav-sub">
                  <RouterLink
                    v-for="subItem in item.subnav"
                    :key="subItem.to"
                    :to="subnavLinkTo(item, subItem)"
                    class="side-nav-sublink"
                    :class="{ 'is-active': isSubnavActive(subItem) }"
                  >
                    {{ subItem.label }}
                  </RouterLink>
                </div>
              </div>
            </div>
          </div>
        </nav>
      </aside>

      <main class="report-content">
        <slot />
      </main>
    </div>
  </div>
</template>
