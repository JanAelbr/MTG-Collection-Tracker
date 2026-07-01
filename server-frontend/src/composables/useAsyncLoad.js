import { ref } from "vue";
import { isApiAbortError } from "../api";

export function useAsyncLoad() {
  const loading = ref(false);
  let activeToken = 0;

  async function run(task) {
    const token = ++activeToken;
    loading.value = true;
    const isCurrent = () => token === activeToken;
    try {
      const result = await task(isCurrent);
      return isCurrent() ? result : undefined;
    } catch (error) {
      if (isApiAbortError(error) || !isCurrent()) {
        return undefined;
      }
      throw error;
    } finally {
      if (isCurrent()) {
        loading.value = false;
      }
    }
  }

  return { loading, run };
}