import { ref } from "vue";

const setGalleryFilter = ref("");

export function useSetGalleryFilter() {
  return { setGalleryFilter };
}
