import { ref } from "vue";
import { isApiAbortError } from "../api";

export function useAsyncLoad() {
  const loading = ref(false);
  let activeToken = 0;

  async function run(task) {
    const token = ++activeToken;
    loading.value = true;
    try {
      return await task();
    } catch (error) {
      if (isApiAbortError(error)) {
        return undefined;
      }
      throw error;
    } finally {
      if (token === activeToken) {
        loading.value = false;
      }
    }
  }

  return { loading, run };
}