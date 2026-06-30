<script setup>
import { onMounted, onUnmounted } from "vue";
import { onError } from "../api";

const messages = defineModel("messages", { type: Array, default: () => [] });

let unsubscribe = null;
let timer = null;

function dismiss(id) {
  messages.value = messages.value.filter((item) => item.id !== id);
}

onMounted(() => {
  unsubscribe = onError((message) => {
    const id = Date.now() + Math.random();
    messages.value = [...messages.value, { id, message }];
    clearTimeout(timer);
    timer = setTimeout(() => dismiss(id), 8000);
  });
});

onUnmounted(() => {
  if (unsubscribe) {
    unsubscribe();
  }
  clearTimeout(timer);
});
</script>

<template>
  <div class="toast-stack" aria-live="assertive">
    <div v-for="item in messages" :key="item.id" class="toast toast-error">
      <span>{{ item.message }}</span>
      <button type="button" class="toast-close" @click="dismiss(item.id)">×</button>
    </div>
  </div>
</template>
