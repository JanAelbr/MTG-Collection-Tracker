<script setup>
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import {
  profileSummary,
  profiles,
  refreshProfiles,
  switchProfile,
} from "../composables/activeProfile";
import { formatEuro } from "../utils/format";
import ProfileAvatar from "../components/ProfileAvatar.vue";
import ProfileEditModal from "../components/ProfileEditModal.vue";

const route = useRoute();
const editing = ref(false);
const editorOpen = ref(false);
const editorProfile = ref(null);

onMounted(async () => {
  await refreshProfiles({ stats: true });
  if (route.query.add === "1") {
    openCreate();
  }
});

function openCreate() {
  editorProfile.value = null;
  editorOpen.value = true;
}

function openEdit(profile) {
  editorProfile.value = profile;
  editorOpen.value = true;
}

async function choose(profile) {
  if (editing.value) {
    openEdit(profile);
    return;
  }
  await switchProfile(profile.id, { href: "/" });
}
</script>

<template>
  <div class="profile-picker">
    <header class="profile-picker-header">
      <h1>Who's collecting?</h1>
      <button type="button" class="btn btn-secondary" @click="editing = !editing">
        {{ editing ? "Done" : "Edit" }}
      </button>
    </header>
    <div class="profile-picker-grid">
      <button
        v-for="profile in profiles"
        :key="profile.id"
        type="button"
        class="profile-picker-tile"
        @click="choose(profile)"
      >
        <ProfileAvatar :profile="profile" size="lg" />
        <strong>{{ profile.name }}</strong>
        <span>{{ profileSummary(profile) }}</span>
        <span v-if="profile.stats">{{ formatEuro(profile.stats.value || 0) }}</span>
      </button>
      <button type="button" class="profile-picker-tile profile-picker-tile--add" @click="openCreate">
        <span class="profile-picker-add">+</span>
        <strong>Add profile</strong>
      </button>
    </div>
    <ProfileEditModal
      :open="editorOpen"
      :profile="editorProfile"
      @close="editorOpen = false"
      @saved="refreshProfiles({ stats: true })"
    />
  </div>
</template>
