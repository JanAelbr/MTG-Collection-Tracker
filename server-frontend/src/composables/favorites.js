import { computed, ref } from "vue";
import { api, clearClientCache, ignoreAborted } from "../api";
import { fetchPricingSettings, usePricingSettings } from "./pricingSettings";
import {
  favoriteArtStyleKey,
  favoriteCardKey,
  cardFavoriteKeyFromCard,
} from "../utils/favorites";

const favoriteCards = ref([]);
const favoriteArtStyles = ref([]);
let loaded = false;

function syncFromSettings(settings) {
  if (!settings) {
    return;
  }
  favoriteCards.value = Array.isArray(settings.favoriteCards) ? settings.favoriteCards : [];
  favoriteArtStyles.value = Array.isArray(settings.favoriteArtStyles)
    ? settings.favoriteArtStyles
    : [];
  loaded = true;
}

export async function fetchFavorites(force = false) {
  if (!force && loaded) {
    return {
      favoriteCards: favoriteCards.value,
      favoriteArtStyles: favoriteArtStyles.value,
    };
  }
  const settings = await fetchPricingSettings(force);
  syncFromSettings(settings);
  return {
    favoriteCards: favoriteCards.value,
    favoriteArtStyles: favoriteArtStyles.value,
  };
}

export function useFavorites() {
  const { settings } = usePricingSettings();

  const favoriteCardKeys = computed(() => {
    const fromSettings = settings.value?.favoriteCards;
    const list = Array.isArray(fromSettings) ? fromSettings : favoriteCards.value;
    return new Set(
      list.map((item) => favoriteCardKey(item.setCode, item.collectorNumber, item.finish)),
    );
  });

  const favoriteArtStyleKeys = computed(() => {
    const fromSettings = settings.value?.favoriteArtStyles;
    const list = Array.isArray(fromSettings) ? fromSettings : favoriteArtStyles.value;
    return new Set(
      list.map((item) => favoriteArtStyleKey(item.setCode, item.artStyle)),
    );
  });

  function isCardFavorite(card, finish = null) {
    const key = cardFavoriteKeyFromCard(card, finish);
    return Boolean(key && favoriteCardKeys.value.has(key));
  }

  function isArtStyleFavorite(setCode, artStyle) {
    const key = favoriteArtStyleKey(setCode, artStyle);
    return Boolean(key && favoriteArtStyleKeys.value.has(key));
  }

  async function toggleCardFavorite(card, finish = null) {
    if (!card?.setCode || card.collectorNumber == null) {
      return null;
    }
    const resolvedFinish = finish == null
      ? (card.finish ?? card.foil ?? 0)
      : finish;
    const result = await ignoreAborted(
      api.toggleFavoriteCard({
        setCode: card.setCode,
        collectorNumber: String(card.collectorNumber),
        finish: resolvedFinish,
      }),
    );
    if (!result) {
      return null;
    }
    favoriteCards.value = result.favoriteCards || [];
    if (settings.value) {
      settings.value = {
        ...settings.value,
        favoriteCards: favoriteCards.value,
      };
    }
    clearClientCache();
    return result;
  }

  async function toggleArtStyleFavorite(setCode, artStyle) {
    if (!setCode || !artStyle) {
      return null;
    }
    const result = await ignoreAborted(
      api.toggleFavoriteArtStyle({
        setCode,
        artStyle,
      }),
    );
    if (!result) {
      return null;
    }
    favoriteArtStyles.value = result.favoriteArtStyles || [];
    if (settings.value) {
      settings.value = {
        ...settings.value,
        favoriteArtStyles: favoriteArtStyles.value,
      };
    }
    clearClientCache();
    return result;
  }

  return {
    favoriteCards,
    favoriteArtStyles,
    favoriteCardKeys,
    favoriteArtStyleKeys,
    isCardFavorite,
    isArtStyleFavorite,
    toggleCardFavorite,
    toggleArtStyleFavorite,
    fetchFavorites,
  };
}
