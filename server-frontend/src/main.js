import { createApp } from "vue";
import { registerSW } from "virtual:pwa-register";
import App from "./App.vue";
import { onProfileNotFound } from "./api";
import { initActiveProfile } from "./composables/activeProfile";
import router from "./router";
import { forgetProfileId, getActiveProfileId } from "./utils/profileSession";
import "./styles/app.css";
import "./styles/profiles.css";

if ("serviceWorker" in navigator) {
  registerSW({ immediate: true });
}

onProfileNotFound(() => {
  forgetProfileId(getActiveProfileId());
  window.location.assign("/profiles");
});

async function start() {
  const { needsPicker } = await initActiveProfile();
  const app = createApp(App).use(router);
  if (needsPicker && window.location.pathname !== "/profiles") {
    await router.replace("/profiles");
  }
  app.mount("#app");
}

start();
