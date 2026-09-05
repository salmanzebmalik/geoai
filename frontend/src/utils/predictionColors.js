const CLASS_PALETTE = [
  '#00c864',
  '#ff8c1a',
  '#3aa0ff',
  '#e152d0',
  '#ffd11a',
  '#22d3d3',
  '#ff5c5c',
  '#9b7bff',
  '#dfbf90',
  '#1414cc',
  '#df90b5',
  '#aaea2a',
  '#bc246b',
  '#ae6432',
  '#bee887',
  '#328dae',
  '#b72aea',
  '#aea232',
  '#2aea36',
  '#324fae',
]

export const DEFAULT_CLASS_COLOR = CLASS_PALETTE[0]

export function colorForClassIndex(index) {
  return CLASS_PALETTE[index % CLASS_PALETTE.length]
}

export function fillColor(hex, alpha = 0.25) {
  const value = hex.replace('#', '')
  const red = Number.parseInt(value.slice(0, 2), 16)
  const green = Number.parseInt(value.slice(2, 4), 16)
  const blue = Number.parseInt(value.slice(4, 6), 16)

  return `rgba(${red}, ${green}, ${blue}, ${alpha})`
}
