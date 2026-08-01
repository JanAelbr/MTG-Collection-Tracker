<script setup>
import { computed } from "vue";

import CardSetSymbol from "./CardSetSymbol.vue";
import {
  binderSeparatorClassNames,
  binderStyleToCssVars,
  DEFAULT_BINDER_SEPARATOR_STYLE,
  normalizeBinderSeparatorStyle,
} from "../utils/binderSeparatorStyle";

const props = defineProps({
  setCode: { type: String, default: "" },
  familyRoot: { type: String, default: "" },
  setName: { type: String, default: "" },
  artStyle: { type: String, default: "" },
  numberRange: { type: String, default: "" },
  seed: { type: String, default: "" },
  styleSettings: {
    type: Object,
    default: () => ({ ...DEFAULT_BINDER_SEPARATOR_STYLE }),
  },
});

/** Stable 32-bit hash so parchment crops stay unique per separator but deterministic. */
function hashString(value) {
  let hash = 2166136261;
  const text = String(value || "");
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function unit(hash, salt) {
  const mixed = Math.imul(hash ^ Math.imul(salt, 0x9e3779b9), 0x85ebca6b) >>> 0;
  return (mixed % 10000) / 10000;
}

function lerp(min, max, t) {
  return min + (max - min) * t;
}

const style = computed(() => normalizeBinderSeparatorStyle(props.styleSettings));

const parchmentSeed = computed(
  () => props.seed || `${props.setCode}|${props.artStyle}|${props.numberRange}|${props.setName}`,
);

const uniqueParchmentVars = computed(() => {
  if (!style.value.uniqueParchment) {
    return {
      "--binder-gold-glow": "0.5",
      "--binder-corner-scale": "1",
      "--parchment-x": "0%",
      "--parchment-y": "0%",
      "--parchment-rot": "0deg",
      "--parchment-scale": "1.15",
      "--parchment-flip": "scale(1, 1)",
    };
  }

  const h = hashString(parchmentSeed.value);
  const u = (salt) => unit(h, salt);
  const flipX = u(10) > 0.5 ? -1 : 1;
  const flipY = u(11) > 0.55 ? -1 : 1;

  return {
    "--binder-gold-glow": lerp(0.35, 0.7, u(3)).toFixed(3),
    "--binder-corner-scale": lerp(0.85, 1.15, u(4)).toFixed(3),
    "--parchment-x": `${lerp(-18, 18, u(5)).toFixed(1)}%`,
    "--parchment-y": `${lerp(-18, 18, u(6)).toFixed(1)}%`,
    "--parchment-rot": `${lerp(-8, 8, u(7)).toFixed(1)}deg`,
    "--parchment-scale": lerp(1.05, 1.45, u(12)).toFixed(3),
    "--parchment-flip": `scale(${flipX}, ${flipY})`,
  };
});

const rootStyle = computed(() => ({
  ...binderStyleToCssVars(style.value),
  ...uniqueParchmentVars.value,
}));

const rootClass = computed(() => binderSeparatorClassNames(style.value));

const showFrame = computed(() => style.value.borderStyle !== "none");
</script>

<template>
  <article
    class="binder-separator"
    :class="rootClass"
    aria-label="Binder separator"
    :style="rootStyle"
  >
    <div class="binder-separator-parchment" aria-hidden="true" />

    <div v-if="showFrame" class="binder-separator-frame" aria-hidden="true">
      <span class="binder-frame-corner binder-frame-corner--tl" />
      <span class="binder-frame-corner binder-frame-corner--tr" />
      <span class="binder-frame-corner binder-frame-corner--bl" />
      <span class="binder-frame-corner binder-frame-corner--br" />
      <span class="binder-frame-jewel binder-frame-jewel--top" />
      <span class="binder-frame-jewel binder-frame-jewel--bottom" />
    </div>

    <div class="binder-separator-inner">
      <div class="binder-separator-icon-wrap">
        <CardSetSymbol
          class="binder-separator-icon"
          :set-code="setCode"
          :family-root="familyRoot"
          variant="generic"
          :size="36"
        />
      </div>
      <h2 class="binder-separator-set">{{ setName }}</h2>
      <p v-if="artStyle" class="binder-separator-art">{{ artStyle }}</p>
      <p v-if="numberRange" class="binder-separator-range">{{ numberRange }}</p>
      <div class="binder-separator-ornament" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </div>
  </article>
</template>
