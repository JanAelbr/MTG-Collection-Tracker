<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, ignoreAborted } from "../api";

const PREVIEW_LIMIT = 5;

const route = useRoute();
const router = useRouter();

const rootRef = ref(null);
const inputRef = ref(null);
const input = ref("");
const query = ref("");
const results = ref([]);
const totalMatches = ref(0);
const loading = ref(false);
const isOpen = ref(false);

let debounceTimer = null;
let requestToken = 0;

const trimmedQuery = computed(() => query.value.trim());
const showDropdown = computed(() => isOpen.value && Boolean(trimmedQuery.value));
const hasMore = computed(() => totalMatches.value > PREVIEW_LIMIT);

function syncFromRoute() {
  if (route.path !== "/collection/search") {
    return;
  }
  const routeQuery = typeof route.query.q === "string" ? route.query.q : "";
  input.value = routeQuery;
  query.value = routeQuery;
}

watch(
  () => [route.path, route.query.q],
  () => {
    syncFromRoute();
  },
  { immediate: true },
);

function scheduleSearch() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(commitSearch, 300);
}

async function commitSearch() {
  query.value = input.value;
  const trimmed = query.value.trim();
  if (!trimmed) {
    results.value = [];
    totalMatches.value = 0;
    loading.value = false;
    return;
  }

  const token = ++requestToken;
  loading.value = true;
  try {
    const payload = await ignoreAborted(api.searchCards({
      q: trimmed,
      setCode: "All",
      ownedFilter: "all",
      foilFilter: "all",
      page: 1,
      pageSize: PREVIEW_LIMIT,
    }));
    if (token !== requestToken || !payload) {
      return;
    }
    results.value = payload.cards || [];
    totalMatches.value = payload.totalMatches ?? 0;
    isOpen.value = true;
  } catch {
    if (token === requestToken) {
      results.value = [];
      totalMatches.value = 0;
    }
  } finally {
    if (token === requestToken) {
      loading.value = false;
    }
  }
}

function openSearchPage(nextQuery = trimmedQuery.value) {
  const trimmed = nextQuery.trim();
  isOpen.value = false;
  router.push({
    path: "/collection/search",
    query: trimmed ? { q: trimmed } : {},
  });
}

function onSubmit() {
  openSearchPage();
}

function onSelectCard(card) {
  const name = card?.name?.trim();
  if (!name) {
    return;
  }
  input.value = name;
  query.value = name;
  openSearchPage(name);
}

function onFocus() {
  isOpen.value = true;
  if (trimmedQuery.value) {
    commitSearch();
  }
}

function onInput() {
  isOpen.value = true;
  scheduleSearch();
}

function onKeydown(event) {
  if (event.key === "Escape") {
    isOpen.value = false;
    inputRef.value?.blur();
  }
}

function onClickOutside(event) {
  if (!rootRef.value?.contains(event.target)) {
    isOpen.value = false;
  }
}

onMounted(() => {
  document.addEventListener("pointerdown", onClickOutside);
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onClickOutside);
  clearTimeout(debounceTimer);
});
</script>

<template>
  <div ref="rootRef" class="navbar-search">
    <form class="navbar-search-form" role="search" @submit.prevent="onSubmit">
      <label class="navbar-search-label" for="navbar-search-input">
        <svg class="navbar-search-icon" viewBox="0 0 20 20" aria-hidden="true">
          <path
            fill="currentColor"
            d="M8.75 2.5a6.25 6.25 0 1 1 0 12.5 6.25 6.25 0 0 1 0-12.5Zm0 1.5a4.75 4.75 0 1 0 0 9.5 4.75 4.75 0 0 0 0-9.5Zm6.86 10.77 2.89 2.89-1.06 1.06-2.89-2.89 1.06-1.06Z"
          />
        </svg>
        <span class="sr-only">Search cards</span>
      </label>
      <input
        id="navbar-search-input"
        ref="inputRef"
        v-model="input"
        type="search"
        class="navbar-search-input"
        placeholder="Search by card name…"
        autocomplete="off"
        aria-label="Search cards"
        :aria-expanded="showDropdown"
        aria-controls="navbar-search-results"
        @focus="onFocus"
        @input="onInput"
        @keydown="onKeydown"
      />
    </form>

    <div
      v-if="showDropdown"
      id="navbar-search-results"
      class="navbar-search-dropdown"
      role="listbox"
      aria-label="Search suggestions"
    >
      <p v-if="loading" class="navbar-search-dropdown-status">Searching…</p>
      <p
        v-else-if="!results.length"
        class="navbar-search-dropdown-status"
      >
        No cards found.
      </p>

      <button
        v-for="card in results"
        :key="`${card.setCode}-${card.collectorNumber}-${card.finish}`"
        type="button"
        class="navbar-search-result"
        role="option"
        @click="onSelectCard(card)"
      >
        <img
          v-if="card.imageUri"
          :src="card.imageUri"
          :alt="card.name"
          class="navbar-search-result-image"
          loading="lazy"
        />
        <div v-else class="navbar-search-result-image navbar-search-result-image--empty" />
        <span class="navbar-search-result-name">{{ card.name }}</span>
      </button>

      <button
        v-if="hasMore && results.length"
        type="button"
        class="navbar-search-more"
        @click="openSearchPage()"
      >
        See all {{ totalMatches }} results
      </button>
      <button
        v-else-if="results.length"
        type="button"
        class="navbar-search-more"
        @click="openSearchPage()"
      >
        Open search page
      </button>
    </div>
  </div>
</template>
