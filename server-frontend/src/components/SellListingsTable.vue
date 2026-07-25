<script setup>
import { computed } from "vue";
import { RouterLink } from "vue-router";
import CardPreview from "./CardPreview.vue";
import CardSetSymbol from "./CardSetSymbol.vue";
import { cardFinish, cardRouteQuery, finishLabel } from "../utils/finishes";
import { formatEuro } from "../utils/format";
import { priceStrategyDescription } from "../utils/priceStrategies";

const props = defineProps({
  tab: { type: String, required: true },
  cards: { type: Array, default: () => [] },
  groups: { type: Array, default: () => [] },
  groupBySet: { type: Boolean, default: false },
  expandedSetCodes: { type: Set, default: () => new Set() },
  priceStrategies: { type: Array, default: () => [] },
  activeStrategyId: { type: String, default: "trend" },
  busyId: { type: [Number, String], default: null },
  sortField: { type: String, default: "name" },
  sortDir: { type: String, default: "asc" },
  strategyValue: { type: Function, required: true },
  askVsActiveDirection: { type: Function, required: true },
  askVsActiveLabel: { type: Function, required: true },
  askVsActiveTitle: { type: Function, required: true },
  profitClass: { type: Function, required: true },
  setGroupMetaText: { type: Function, required: true },
});

const emit = defineEmits([
  "toggle-sort",
  "toggle-set-group",
  "save-listed-price",
  "save-sold-price",
  "open-sell",
  "unlist",
  "delete-sold",
]);

const columnCount = computed(() => {
  if (props.tab === "listed") {
    return 7 + props.priceStrategies.length;
  }
  return 8;
});

const displayRows = computed(() => {
  if (!props.groupBySet) {
    return props.cards.map((card) => ({
      key: `card-${card.listingId}`,
      kind: "card",
      card,
      hidden: false,
    }));
  }
  const rows = [];
  for (const group of props.groups) {
    const expanded = props.expandedSetCodes.has(group.setCode);
    rows.push({
      key: `group-${group.setCode}`,
      kind: "group",
      group,
      expanded,
    });
    for (const card of group.cards) {
      rows.push({
        key: `card-${card.listingId}`,
        kind: "card",
        card,
        hidden: !expanded,
      });
    }
  }
  return rows;
});

function cardRoute(card) {
  return {
    name: "card",
    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
    query: cardRouteQuery(cardFinish(card)),
  };
}

function sortIndicator(field) {
  if (props.sortField !== field) {
    return "";
  }
  return props.sortDir === "asc" ? " ↑" : " ↓";
}

function sortHeaderClass(field) {
  return {
    "is-sortable": true,
    "is-sorted": props.sortField === field,
  };
}
</script>

<template>
  <table class="reports-table sell-table" :class="{ 'is-grouped': groupBySet }">
    <thead>
      <tr>
        <th :class="sortHeaderClass('name')">
          <button type="button" class="sell-table-sort-btn" @click="emit('toggle-sort', 'name')">
            Card{{ sortIndicator("name") }}
          </button>
        </th>
        <th :class="sortHeaderClass('set')">
          <button type="button" class="sell-table-sort-btn" @click="emit('toggle-sort', 'set')">
            Set{{ sortIndicator("set") }}
          </button>
        </th>
        <th :class="sortHeaderClass('finish')">
          <button type="button" class="sell-table-sort-btn" @click="emit('toggle-sort', 'finish')">
            Finish{{ sortIndicator("finish") }}
          </button>
        </th>
        <th v-if="tab === 'listed'" :class="sortHeaderClass('listingPrice')">
          <button type="button" class="sell-table-sort-btn" @click="emit('toggle-sort', 'listingPrice')">
            Asking{{ sortIndicator("listingPrice") }}
          </button>
        </th>
        <th v-if="tab === 'listed'" :class="sortHeaderClass('askDelta')">
          <button
            type="button"
            class="sell-table-sort-btn"
            :title="`Difference vs ${priceStrategies.find((row) => row.id === activeStrategyId)?.label || 'active'} strategy`"
            @click="emit('toggle-sort', 'askDelta')"
          >
            vs{{ sortIndicator("askDelta") }}
          </button>
        </th>
        <template v-if="tab === 'listed'">
          <th
            v-for="strategy in priceStrategies"
            :key="strategy.id"
            class="sell-strategy-col"
            :class="{
              ...sortHeaderClass(`strategy:${strategy.id}`),
              'is-active-strategy': strategy.id === activeStrategyId,
            }"
            :title="priceStrategyDescription(strategy.id)"
          >
            <button
              type="button"
              class="sell-table-sort-btn"
              @click="emit('toggle-sort', `strategy:${strategy.id}`)"
            >
              {{ strategy.label }}{{ sortIndicator(`strategy:${strategy.id}`) }}
            </button>
          </th>
        </template>
        <th v-if="tab === 'sold'" :class="sortHeaderClass('salePrice')">
          <button type="button" class="sell-table-sort-btn" @click="emit('toggle-sort', 'salePrice')">
            Sale{{ sortIndicator("salePrice") }}
          </button>
        </th>
        <th v-if="tab === 'sold'" :class="sortHeaderClass('purchaseValue')">
          <button type="button" class="sell-table-sort-btn" @click="emit('toggle-sort', 'purchaseValue')">
            Paid{{ sortIndicator("purchaseValue") }}
          </button>
        </th>
        <th v-if="tab === 'sold'" :class="sortHeaderClass('profitLoss')">
          <button type="button" class="sell-table-sort-btn" @click="emit('toggle-sort', 'profitLoss')">
            P/L{{ sortIndicator("profitLoss") }}
          </button>
        </th>
        <th :class="sortHeaderClass('location')">
          <button type="button" class="sell-table-sort-btn" @click="emit('toggle-sort', 'location')">
            Location{{ sortIndicator("location") }}
          </button>
        </th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      <template v-for="row in displayRows" :key="row.key">
        <tr v-if="row.kind === 'group'" class="sell-set-group-row">
          <td :colspan="columnCount">
            <button
              type="button"
              class="storage-set-group-header sell-set-group-header"
              :class="{ 'is-collapsed': !row.expanded }"
              :aria-expanded="row.expanded"
              @click="emit('toggle-set-group', row.group.setCode)"
            >
              <span class="storage-set-group-chevron" aria-hidden="true">▾</span>
              <CardSetSymbol :set-code="row.group.setCode" variant="generic" :size="18" />
              <h3 class="storage-set-group-title">{{ row.group.setLabel || row.group.setCode }}</h3>
              <span class="storage-set-group-meta">{{ setGroupMetaText(row.group) }}</span>
            </button>
          </td>
        </tr>
        <tr v-else v-show="!row.hidden">
          <td>
            <CardPreview
              :image-uri="row.card.imageUri || ''"
              :image-uri-back="row.card.imageUriBack || ''"
            >
              <span class="sell-card-name">
                <CardSetSymbol :set-code="row.card.setCode" :rarity="row.card.rarity || ''" />
                <RouterLink :to="cardRoute(row.card)" class="reports-card-link">
                  {{ row.card.name }}
                </RouterLink>
              </span>
            </CardPreview>
          </td>
          <td>
            <span class="sell-set-cell">
              <CardSetSymbol :set-code="row.card.setCode" variant="generic" :size="16" />
              <span>{{ row.card.setLabel || row.card.setCode }} · #{{ row.card.collectorNumber }}</span>
            </span>
          </td>
          <td>{{ finishLabel(row.card.finish) }}</td>
          <td v-if="tab === 'listed'">
            <span class="sell-ask-cell">
              <input
                class="sell-price-input"
                type="number"
                min="0"
                step="0.01"
                :value="row.card.listingPrice"
                :disabled="busyId === row.card.listingId"
                @change="emit('save-listed-price', row.card, $event)"
              >
            </span>
          </td>
          <td v-if="tab === 'listed'" class="sell-ask-delta-cell">
            <button
              v-if="askVsActiveDirection(row.card)"
              type="button"
              class="sell-ask-delta"
              :class="askVsActiveDirection(row.card) === 'up' ? 'is-up' : 'is-down'"
              :title="askVsActiveTitle(row.card)"
              @click="emit('toggle-sort', 'askDelta')"
            >
              <span aria-hidden="true">{{ askVsActiveDirection(row.card) === "up" ? "↑" : "↓" }}</span>
              <span>{{ askVsActiveLabel(row.card) }}</span>
            </button>
            <span v-else class="sell-ask-delta is-flat">—</span>
          </td>
          <template v-if="tab === 'listed'">
            <td
              v-for="strategy in priceStrategies"
              :key="`${row.card.listingId}-${strategy.id}`"
              class="sell-strategy-col"
              :class="{ 'is-active-strategy': strategy.id === activeStrategyId }"
            >
              {{ formatEuro(strategyValue(row.card, strategy.id)) }}
            </td>
          </template>
          <td v-if="tab === 'sold'">
            <input
              class="sell-price-input"
              type="number"
              min="0"
              step="0.01"
              :value="row.card.salePrice"
              :disabled="busyId === row.card.listingId"
              @change="emit('save-sold-price', row.card, $event)"
            >
          </td>
          <td v-if="tab === 'sold'">{{ formatEuro(row.card.purchaseValue) }}</td>
          <td v-if="tab === 'sold'" :class="profitClass(row.card.profitLoss)">
            {{ formatEuro(row.card.profitLoss) }}
          </td>
          <td>{{ row.card.locationLabel || row.card.locationSlug || "—" }}</td>
          <td class="sell-actions">
            <template v-if="tab === 'listed'">
              <button
                type="button"
                class="btn btn-primary btn-compact"
                :disabled="busyId === row.card.listingId"
                @click="emit('open-sell', row.card)"
              >
                Sold
              </button>
              <button
                type="button"
                class="btn btn-secondary btn-compact"
                :disabled="busyId === row.card.listingId"
                @click="emit('unlist', row.card)"
              >
                Unlist
              </button>
            </template>
            <button
              v-else
              type="button"
              class="btn btn-secondary btn-compact"
              :disabled="busyId === row.card.listingId"
              @click="emit('delete-sold', row.card)"
            >
              Remove
            </button>
          </td>
        </tr>
      </template>
    </tbody>
  </table>
</template>
