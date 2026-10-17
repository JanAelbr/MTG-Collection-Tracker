<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { api } from "../api";
import {
  activeProfile,
  profileSummary,
  profiles,
  refreshProfiles,
  switchProfile,
} from "../composables/activeProfile";
import ProfileAvatar from "./ProfileAvatar.vue";

const router = useRouter();
const open = ref(false);
const root = ref(null);
const activeIndex = ref(0);

const others = computed(() =>
  profiles.value.filter((profile) => profile.id !== activeProfile.value?.id),
);

const items = computed(() => {
  const rows = others.value.map((profile) => ({
    id: `switch:${profile.id}`,
    label: profile.name,
    profile,
    run: () => switchProfile(profile.id),
  }));
  rows.push(
    { id: "add", label: "Add profile", run: () => router.push({ path: "/profiles", query: { add: "1" } }) },
    { id: "manage", label: "Manage profiles", run: () => router.push("/settings/profiles") },
    {
      id: "export",
      label: "Export this profile",
      disabled: !activeProfile.value,
      run: () => api.exportProfile(activeProfile.value.id),
    },
  );
  return rows;
});

function close() {
  open.value = false;
}

async function toggle() {
  open.value = !open.value;
  if (open.value) {
    activeIndex.value = 0;
    try {
      await refreshProfiles({ stats: true });
    } catch {
      // The menu still lists the profiles loaded at startup.
    }
  }
}

function onDocumentPointer(event) {
  if (!open.value || root.value?.contains(event.target)) {
    return;
  }
  close();
}

function onKeydown(event) {
  if (!open.value) {
    if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggle();
    }
    return;
  }
  if (event.key === "Escape") {
    event.preventDefault();
    close();
    return;
  }
  if (event.key === "ArrowDown") {
    event.preventDefault();
    activeIndex.value = (activeIndex.value + 1) % items.value.length;
    return;
  }
  if (event.key === "ArrowUp") {
    event.preventDefault();
    activeIndex.value = (activeIndex.value - 1 + items.value.length) % items.value.length;
    return;
  }
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    const item = items.value[activeIndex.value];
    if (item && !item.disabled) {
      close();
      item.run();
    }
  }
}

watch(open, (isOpen) => {
  if (isOpen) {
    document.addEventListener("pointerdown", onDocumentPointer);
  } else {
    document.removeEventListener("pointerdown", onDocumentPointer);
  }
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onDocumentPointer);
});
</script>

<template>
  <div v-if="activeProfile" ref="root" class="profile-switcher">
    <button
      type="button"
      class="profile-switcher-button"
      :aria-expanded="open"
      aria-haspopup="menu"
      @click="toggle"
      @keydown="onKeydown"
    >
      <ProfileAvatar :profile="activeProfile" size="sm" />
      <span class="profile-switcher-name">{{ activeProfile.name }}</span>
    </button>
    <div
      v-if="open"
      class="card-context-menu profile-switcher-menu"
      role="menu"
      @keydown="onKeydown"
    >
      <div class="profile-switcher-current" role="presentation">
        <ProfileAvatar :profile="activeProfile" size="md" />
        <span>
          <strong>{{ activeProfile.name }}</strong>
          <small>{{ profileSummary(activeProfile) || "Current profile" }}</small>
        </span>
      </div>
      <div class="card-context-menu-divider" />
      <button
        v-for="(item, index) in items"
        :key="item.id"
        type="button"
        class="card-context-menu-item"
        role="menuitem"
        :class="{ 'is-selected': index === activeIndex }"
        :disabled="item.disabled"
        @mouseenter="activeIndex = index"
        @click="close(); item.run()"
      >
        <ProfileAvatar v-if="item.profile" :profile="item.profile" size="sm" />
        <span>{{ item.label }}</span>
      </button>
    </div>
  </div>
</template>
