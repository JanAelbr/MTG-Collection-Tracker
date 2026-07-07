import { createApp } from "vue";
import { registerSW } from "virtual:pwa-register";
import App from "./App.vue";
import router from "./router";
import "./styles/app.css";

if ("serviceWorker" in navigator) {
  registerSW({ immediate: true });
}

createApp(App).use(router).mount("#app");
