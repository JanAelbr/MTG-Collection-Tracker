<script setup>
import { computed, ref, watch } from "vue";
import { api } from "../api";
import { createProfile, profiles, refreshProfiles, updateProfile } from "../composables/activeProfile";
import { PROFILE_COLOR_KEYS, profileColor } from "../utils/profileColors";
import ProfileAvatar from "./ProfileAvatar.vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  profile: { type: Object, default: null },
});
const emit = defineEmits(["close", "saved"]);

const name = ref("");
const color = ref("indigo");
const avatar = ref("");
const source = ref("blank");
const copyFrom = ref("");
const file = ref(null);
const preview = ref(null);
const error = ref("");
const busy = ref(false);

const editing = computed(() => Boolean(props.profile?.id));
const draft = computed(() => ({
  name: name.value || "New profile",
  color: color.value,
  avatar: avatar.value,
}));
const copyOptions = computed(() =>
  profiles.value.filter((profile) => profile.id !== props.profile?.id),
);

watch(() => props.open, (isOpen) => {
  if (!isOpen) {
    return;
  }
  name.value = props.profile?.name || "";
  color.value = props.profile?.color || PROFILE_COLOR_KEYS[profiles.value.length % PROFILE_COLOR_KEYS.length];
  avatar.value = props.profile?.avatar || "";
  source.value = "blank";
  copyFrom.value = copyOptions.value[0]?.id || "";
  file.value = null;
  preview.value = null;
  error.value = "";
  busy.value = false;
});

async function onFile(event) {
  const next = event.target.files?.[0] || null;
  file.value = next;
  preview.value = null;
  error.value = "";
  if (!next) {
    return;
  }
  try {
    preview.value = await api.previewCollectionBackup(next);
    if (!name.value && preview.value?.profile?.name) {
      name.value = preview.value.profile.name;
    }
    if (preview.value?.profile?.color) {
      color.value = preview.value.profile.color;
    }
  } catch (err) {
    error.value = err.message || "Could not read that backup.";
    file.value = null;
  }
}

async function save() {
  error.value = "";
  busy.value = true;
  try {
    let saved;
    if (editing.value) {
      saved = await updateProfile(props.profile.id, {
        name: name.value,
        color: color.value,
        avatar: avatar.value,
      });
    } else if (source.value === "duplicate") {
      saved = await createProfile({
        name: name.value,
        color: color.value,
        avatar: avatar.value,
        copyFrom: copyFrom.value,
      });
    } else if (source.value === "import") {
      if (!file.value) {
        error.value = "Choose a backup file.";
        return;
      }
      const imported = await api.importProfile(file.value, { name: name.value, color: color.value });
      await refreshProfiles({ stats: true });
      saved = imported.profile;
    } else {
      saved = await createProfile({
        name: name.value,
        color: color.value,
        avatar: avatar.value,
      });
    }
    emit("saved", saved);
    emit("close");
  } catch (err) {
    error.value = err.message || "Could not save the profile.";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div v-if="open" class="modal-backdrop" @click.self="emit('close')">
    <form class="modal-card profile-edit-modal" @submit.prevent="save">
      <h3>{{ editing ? "Edit profile" : "New profile" }}</h3>
      <div class="profile-edit-preview">
        <ProfileAvatar :profile="draft" size="lg" />
      </div>
      <label class="manager-filter">
        <span>Name</span>
        <input v-model="name" type="text" maxlength="40" required autofocus />
      </label>
      <fieldset class="profile-color-swatches">
        <legend>Colour</legend>
        <button
          v-for="key in PROFILE_COLOR_KEYS"
          :key="key"
          type="button"
          class="profile-color-swatch"
          :class="{ 'is-selected': color === key }"
          :style="{ background: profileColor(key).accent }"
          :aria-label="profileColor(key).label"
          @click="color = key"
        />
      </fieldset>
      <label class="manager-filter">
        <span>Avatar</span>
        <input
          v-model="avatar"
          type="text"
          maxlength="4"
          placeholder="Initials or emoji"
        />
      </label>

      <fieldset v-if="!editing" class="profile-source">
        <legend>Start from</legend>
        <label><input v-model="source" type="radio" value="blank" /> Blank collection</label>
        <label :class="{ 'is-disabled': !copyOptions.length }">
          <input v-model="source" type="radio" value="duplicate" :disabled="!copyOptions.length" />
          Duplicate an existing profile
        </label>
        <label v-if="source === 'duplicate'">
          <span class="sr-only">Profile to copy</span>
          <select v-model="copyFrom">
            <option v-for="option in copyOptions" :key="option.id" :value="option.id">
              {{ option.name }}
            </option>
          </select>
        </label>
        <label><input v-model="source" type="radio" value="import" /> Import a backup file</label>
        <label v-if="source === 'import'" class="home-backup-file">
          <span>Backup file</span>
          <input type="file" accept=".zip,.mtgbackup.zip" @change="onFile" />
        </label>
        <ul v-if="preview?.summary" class="profile-import-preview">
          <li>{{ preview.summary.purchases }} owned prints</li>
          <li>{{ preview.summary.decks }} decks</li>
          <li>{{ preview.summary.cardInstances }} stored copies</li>
        </ul>
      </fieldset>

      <p v-if="error" class="home-sync-message error">{{ error }}</p>
      <div class="modal-actions">
        <button type="button" class="btn btn-secondary" :disabled="busy" @click="emit('close')">
          Cancel
        </button>
        <button type="submit" class="btn btn-primary" :disabled="busy || !name.trim()">
          {{ busy ? "Saving…" : (editing ? "Save" : "Create") }}
        </button>
      </div>
    </form>
  </div>
</template>
