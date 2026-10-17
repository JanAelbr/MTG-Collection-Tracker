<script setup>
import { onMounted, ref } from "vue";
import { api } from "../api";
import { confirmDialog } from "../composables/confirmDialog";
import {
  activeProfile,
  createProfile,
  deleteProfile,
  profiles,
  refreshProfiles,
  switchProfile,
  updateProfile,
} from "../composables/activeProfile";
import { formatEuro } from "../utils/format";
import ProfileAvatar from "../components/ProfileAvatar.vue";
import ProfileEditModal from "../components/ProfileEditModal.vue";

const message = ref("");
const error = ref("");
const editorOpen = ref(false);
const editorProfile = ref(null);
const importInput = ref(null);

onMounted(() => {
  refreshProfiles({ stats: true }).catch((err) => {
    error.value = err.message || "Could not load profiles.";
  });
});

function openCreate() {
  editorProfile.value = null;
  editorOpen.value = true;
}

function openEdit(profile) {
  editorProfile.value = profile;
  editorOpen.value = true;
}

function formatLastUsed(value) {
  if (!value) {
    return "Never used";
  }
  const then = new Date(value);
  if (Number.isNaN(then.getTime())) {
    return value;
  }
  return `Last used ${then.toLocaleString()}`;
}

function statsLine(profile) {
  const stats = profile.stats || {};
  const copies = Number(stats.ownedCopies || 0);
  const decks = Number(stats.decks || 0);
  return `${copies} card${copies === 1 ? "" : "s"} · ${decks} deck${decks === 1 ? "" : "s"} · ${formatEuro(stats.value || 0)}`;
}

async function duplicate(profile) {
  error.value = "";
  try {
    await createProfile({ name: `${profile.name} copy`, copyFrom: profile.id, color: profile.color });
    message.value = `Duplicated ${profile.name}.`;
  } catch (err) {
    error.value = err.message || "Could not duplicate that profile.";
  }
}

async function makeDefault(profile) {
  error.value = "";
  try {
    await updateProfile(profile.id, { isDefault: true });
    message.value = `${profile.name} is the default profile.`;
  } catch (err) {
    error.value = err.message || "Could not update the default profile.";
  }
}

async function remove(profile) {
  const ok = await confirmDialog({
    title: `Delete ${profile.name}?`,
    message: "The collection moves to the trash and can be recovered from the profiles folder. This cannot be undone from the app.",
    confirmLabel: "Delete profile",
    danger: true,
    requireText: profile.name,
  });
  if (!ok) {
    return;
  }
  error.value = "";
  try {
    await deleteProfile(profile.id);
    message.value = `Deleted ${profile.name}.`;
  } catch (err) {
    error.value = err.message || "Could not delete that profile.";
  }
}

async function onImportFile(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) {
    return;
  }
  error.value = "";
  try {
    const imported = await api.importProfile(file);
    await refreshProfiles({ stats: true });
    message.value = `Imported ${imported.profile?.name || "profile"}.`;
  } catch (err) {
    error.value = err.message || "Could not import that backup.";
  }
}
</script>

<template>
  <div class="home-page">
    <section class="home-panel">
      <div class="profile-settings-heading">
        <h2>Profiles</h2>
        <div class="profile-settings-actions">
          <button type="button" class="btn btn-secondary" @click="importInput?.click()">
            Import profile from backup
          </button>
          <button type="button" class="btn btn-primary" @click="openCreate">New profile</button>
          <input
            ref="importInput"
            class="sr-only"
            type="file"
            accept=".zip,.mtgbackup.zip"
            @change="onImportFile"
          />
        </div>
      </div>
      <p class="home-intro">
        Each profile has its own cards, decks, storage, and settings. The card catalog and prices are shared.
      </p>
      <ul class="profile-settings-list">
        <li v-for="profile in profiles" :key="profile.id" class="profile-settings-row">
          <ProfileAvatar :profile="profile" size="md" />
          <div class="profile-settings-copy">
            <strong>
              {{ profile.name }}
              <span v-if="profile.isDefault" class="profile-settings-badge">Default</span>
              <span v-if="profile.id === activeProfile?.id" class="profile-settings-badge">Current</span>
            </strong>
            <span>{{ statsLine(profile) }}</span>
            <span>{{ formatLastUsed(profile.lastUsedAt) }}</span>
          </div>
          <div class="profile-settings-row-actions">
            <button
              type="button"
              class="btn btn-secondary"
              :disabled="profile.id === activeProfile?.id"
              @click="switchProfile(profile.id)"
            >
              Switch
            </button>
            <button type="button" class="btn btn-secondary" @click="openEdit(profile)">Edit</button>
            <button type="button" class="btn btn-secondary" @click="duplicate(profile)">Duplicate</button>
            <button type="button" class="btn btn-secondary" @click="api.exportProfile(profile.id)">Export</button>
            <button
              type="button"
              class="btn btn-secondary"
              :disabled="profile.isDefault"
              @click="makeDefault(profile)"
            >
              Set default
            </button>
            <button
              type="button"
              class="btn btn-secondary"
              :disabled="profiles.length <= 1"
              @click="remove(profile)"
            >
              Delete
            </button>
          </div>
        </li>
      </ul>
      <p v-if="message" class="home-sync-message">{{ message }}</p>
      <p v-if="error" class="home-sync-message error">{{ error }}</p>
    </section>
    <ProfileEditModal
      :open="editorOpen"
      :profile="editorProfile"
      @close="editorOpen = false"
    />
  </div>
</template>
