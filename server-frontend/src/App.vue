<script setup>
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import AppLayout from "./components/AppLayout.vue";
import CardImageTooltip from "./components/CardImageTooltip.vue";
import ProfileAvatar from "./components/ProfileAvatar.vue";
import ToastContainer from "./components/ToastContainer.vue";
import { switchingTo } from "./composables/activeProfile";

const route = useRoute();
const toastMessages = ref([]);
const bare = computed(() => route.meta.bare === true);
</script>

<template>
  <div v-if="switchingTo" class="profile-switch-overlay">
    <ProfileAvatar :profile="switchingTo" size="md" />
    <span>Switching to {{ switchingTo.name }}</span>
  </div>
  <RouterView v-if="bare" />
  <AppLayout v-else>
    <RouterView v-slot="{ Component }">
      <KeepAlive :include="['DecksView']" :max="3">
        <component :is="Component" />
      </KeepAlive>
    </RouterView>
  </AppLayout>
  <ToastContainer v-model:messages="toastMessages" />
  <CardImageTooltip />
</template>
