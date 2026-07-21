<script setup>
import AppLayout from "./components/AppLayout.vue";
import CardImageTooltip from "./components/CardImageTooltip.vue";
import ToastContainer from "./components/ToastContainer.vue";
import { ref } from "vue";

const toastMessages = ref([]);
</script>

<template>
  <AppLayout>
    <RouterView v-slot="{ Component }">
      <KeepAlive :include="['DecksView']" :max="3">
        <component :is="Component" />
      </KeepAlive>
    </RouterView>
  </AppLayout>
  <ToastContainer v-model:messages="toastMessages" />
  <CardImageTooltip />
</template>
