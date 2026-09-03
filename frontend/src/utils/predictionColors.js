// Shared palette for zero-shot prediction classes.
// Map.vue styles the polygons and Legend.vue draws the swatches, so both have to
// derive the same colour for the same class - keep the lookup in one place.

// The first entry is the green the map used before multi-class support, so a
// single-class prediction still looks the way it always did.
const CLASS_PALETTE = [
  '#00c864',
  '#ff8c1a',
  '#3aa0ff',
  '#e152d0',
  '#ffd11a',
  '#22d3d3',
  '#ff5c5c',
  '#9b7bff',
]

export const DEFAULT_CLASS_COLOR = CLASS_PALETTE[0]

// Palette colour for the n-th class of a prediction; wraps around for long lists.
export function colorForClassIndex(index) {
  return CLASS_PALETTE[index % CLASS_PALETTE.length]
}

// Translucent variant of a palette colour, used as polygon fill.
export function fillColor(hex, alpha = 0.25) {
  const value = hex.replace('#', '')
  const red = Number.parseInt(value.slice(0, 2), 16)
  const green = Number.parseInt(value.slice(2, 4), 16)
  const blue = Number.parseInt(value.slice(4, 6), 16)

  return `rgba(${red}, ${green}, ${blue}, ${alpha})`
}
