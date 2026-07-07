export const STORAGE_LOCATION_SECTIONS = [
  { type: "storage", label: "Storage" },
  { type: "binder", label: "Binders" },
  { type: "deck", label: "Decks" },
];

function compareLocations(left, right) {
  const orderLeft = left.sortOrder ?? 0;
  const orderRight = right.sortOrder ?? 0;
  if (orderLeft !== orderRight) {
    return orderLeft - orderRight;
  }
  return String(left.label).localeCompare(String(right.label));
}

export function groupStorageLocations(locations) {
  const sorted = [...locations].sort(compareLocations);
  return STORAGE_LOCATION_SECTIONS.map((section) => ({
    ...section,
    locations: sorted.filter((location) => location.locationType === section.type),
  })).filter((section) => section.locations.length > 0);
}

export function findStorageLocation(locations, slug) {
  if (!slug) {
    return null;
  }
  return locations.find((location) => location.slug === slug) || null;
}
