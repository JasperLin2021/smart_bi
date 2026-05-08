export const CHART_COLOR_PALETTE = [
  "#0f766e",
  "#3b82f6",
  "#f59e0b",
  "#8b5cf6",
  "#ef4444",
  "#10b981",
  "#f97316",
  "#06b6d4",
  "#ec4899",
  "#84cc16",
]

export const PRIMARY_CHART_COLOR = CHART_COLOR_PALETTE[0]

export type ChartBorderRadius = number | number[]

export const chartColorAt = (index: number) => {
  const normalized = ((index % CHART_COLOR_PALETTE.length) + CHART_COLOR_PALETTE.length) % CHART_COLOR_PALETTE.length
  return CHART_COLOR_PALETTE[normalized]
}

export const colorizeCategoryData = <T>(values: T[], borderRadius?: ChartBorderRadius) =>
  values.map((value, index) => ({
    value,
    itemStyle: {
      color: values.length > 1 ? chartColorAt(index) : PRIMARY_CHART_COLOR,
      ...(borderRadius !== undefined ? { borderRadius } : {}),
    },
  }))

export const makeAreaGradient = (color = PRIMARY_CHART_COLOR) => ({
  type: "linear",
  x: 0,
  y: 0,
  x2: 0,
  y2: 1,
  colorStops: [
    { offset: 0, color: `${color}55` },
    { offset: 1, color: `${color}08` },
  ],
})
