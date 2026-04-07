/**
 * Theme-aware colors for WebGL canvas rendering (visualization-tab).
 * WebGL cannot read CSS custom properties, so these are kept as raw values.
 * Update these when Tailwind theme colors change.
 */
export const GRAPH_THEME = {
  dark: { bg: "#09090b", dim: "#1f2937", linkBase: "140,180,255", linkDim: "255,255,255" },
  light: { bg: "#f8fafc", dim: "#d1d5db", linkBase: "59,130,246", linkDim: "0,0,0" },
} as const
