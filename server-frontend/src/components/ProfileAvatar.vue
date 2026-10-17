<script setup>
import { computed } from "vue";
import { profileAvatarText, profileColor } from "../utils/profileColors";

const props = defineProps({
  profile: { type: Object, required: true },
  size: { type: String, default: "md" },
});

const style = computed(() => {
  const color = profileColor(props.profile?.color);
  return {
    background: color.soft,
    color: color.accent,
  };
});

const label = computed(() => profileAvatarText(props.profile));
</script>

<template>
  <span
    class="profile-avatar"
    :class="`profile-avatar--${size}`"
    :style="style"
    aria-hidden="true"
  >{{ label }}</span>
</template>
