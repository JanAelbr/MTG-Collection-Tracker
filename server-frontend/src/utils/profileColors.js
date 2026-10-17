// Palette keys match util/profile_registry.PROFILE_COLORS on the server.
export const PROFILE_COLORS = Object.freeze({
  indigo: { label: "Indigo", accent: "#6366f1", soft: "rgba(99, 102, 241, 0.18)" },
  teal: { label: "Teal", accent: "#14b8a6", soft: "rgba(20, 184, 166, 0.18)" },
  emerald: { label: "Emerald", accent: "#10b981", soft: "rgba(16, 185, 129, 0.18)" },
  amber: { label: "Amber", accent: "#f59e0b", soft: "rgba(245, 158, 11, 0.2)" },
  orange: { label: "Orange", accent: "#f97316", soft: "rgba(249, 115, 22, 0.18)" },
  rose: { label: "Rose", accent: "#f43f5e", soft: "rgba(244, 63, 94, 0.18)" },
  violet: { label: "Violet", accent: "#8b5cf6", soft: "rgba(139, 92, 246, 0.18)" },
  sky: { label: "Sky", accent: "#0ea5e9", soft: "rgba(14, 165, 233, 0.18)" },
  slate: { label: "Slate", accent: "#64748b", soft: "rgba(100, 116, 139, 0.2)" },
  lime: { label: "Lime", accent: "#84cc16", soft: "rgba(132, 204, 22, 0.2)" },
});

export const PROFILE_COLOR_KEYS = Object.freeze(Object.keys(PROFILE_COLORS));

export function profileColor(key) {
  return PROFILE_COLORS[key] || PROFILE_COLORS.indigo;
}

export function profileInitials(name) {
  const words = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (!words.length) {
    return "?";
  }
  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase();
  }
  return `${words[0][0]}${words[words.length - 1][0]}`.toUpperCase();
}

export function profileAvatarText(profile) {
  return String(profile?.avatar || "").trim() || profileInitials(profile?.name);
}
