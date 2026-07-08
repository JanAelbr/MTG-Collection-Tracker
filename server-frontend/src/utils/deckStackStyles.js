const STACK_COLOR_STYLES = {
  W: {
    background: "linear-gradient(90deg, #faf6eb 0%, #efe4cc 100%)",
    borderColor: "#d8c39a",
    color: "#3e3628",
  },
  U: {
    background: "linear-gradient(90deg, #e8f3fc 0%, #b9daf5 100%)",
    borderColor: "#7eb8e8",
    color: "#16324f",
  },
  B: {
    background: "linear-gradient(90deg, #4a4a4a 0%, #2b2b2b 100%)",
    borderColor: "#1a1a1a",
    color: "#f2f2f2",
  },
  R: {
    background: "linear-gradient(90deg, #fde8e8 0%, #f4a5a5 100%)",
    borderColor: "#e57373",
    color: "#5c1f1f",
  },
  G: {
    background: "linear-gradient(90deg, #e8f5e9 0%, #a5d6a7 100%)",
    borderColor: "#66bb6a",
    color: "#1b4332",
  },
  C: {
    background: "linear-gradient(90deg, #f5f5f5 0%, #e0e0e0 100%)",
    borderColor: "#bdbdbd",
    color: "#424242",
  },
};

const MULTICOLOR_STYLE = {
  background: "linear-gradient(90deg, #f7efd6 0%, #d4b56a 55%, #f7efd6 100%)",
  borderColor: "#c9a227",
  color: "#3b2f14",
};

export function deckStackRowStyle(card) {
  const colors = card?.colors?.length ? card.colors : ["C"];
  if (colors.length >= 2) {
    return { ...MULTICOLOR_STYLE };
  }
  const key = colors[0];
  return { ...(STACK_COLOR_STYLES[key] || STACK_COLOR_STYLES.C) };
}
