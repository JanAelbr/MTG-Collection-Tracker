<script setup>
import { useRoute } from "vue-router";

const route = useRoute();
</script>

<template>
  <section class="placeholder-view">
    <h2>{{ route.meta.title }}</h2>
    <p>Coming soon — use the static reports in <code>reports/</code> for now.</p>
  </section>
</template>
