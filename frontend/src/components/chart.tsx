import * as React from "react"

import { useTheme } from "@/lib/theme-context"

export type Figure = {
  data: Record<string, unknown>[]
  layout: Record<string, unknown>
}

// The three Plotly functions used here. The API's figures are plain JSON, so
// they are passed through as they are.
type PlotlyApi = {
  react: (element: HTMLElement, data: unknown[], layout: unknown, config?: unknown) => Promise<unknown>
  purge: (element: HTMLElement) => void
  Plots: { resize: (element: HTMLElement) => void }
}

let plotly: Promise<PlotlyApi> | undefined

// Plotly is large, so it is fetched once, when the first chart appears.
function loadPlotly(): Promise<PlotlyApi> {
  if (!plotly) {
    // The cartesian build has the chart types used here (lines, bars, heat maps)
    // and is about a third of the size of the full library.
    plotly = import("plotly.js-cartesian-dist-min").then(
      (module) => module.default as unknown as PlotlyApi,
    )
  }
  return plotly
}

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim()
}

function withOpacity(hex: string, opacity: string): string {
  const value = Number.parseInt(hex.slice(1), 16)
  return `rgba(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}, ${opacity})`
}

const SCALES: Record<string, () => [number, string][]> = {
  "scale-sequential": () =>
    [1, 2, 3, 4, 5].map((step, index) => [index / 4, token(`chart-ramp-${step}`)]),
  "scale-diverging": () => [
    [0, token("chart-down")],
    [0.5, token("chart-midpoint")],
    [1, token("chart-1")],
  ],
}

/**
 * The API names colours instead of fixing them: "token:chart-1" is the
 * --chart-1 colour of the theme, "token:chart-1@0.2" the same at 20% opacity.
 */
function resolveTokens(value: unknown): unknown {
  if (typeof value === "string" && value.startsWith("token:")) {
    const [name, opacity] = value.slice(6).split("@")
    if (name in SCALES) return SCALES[name]()
    return opacity ? withOpacity(token(name), opacity) : token(name)
  }
  if (Array.isArray(value)) return value.map(resolveTokens)
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, resolveTokens(item)]),
    )
  }
  return value
}

function merge(base: Record<string, unknown>, extra: Record<string, unknown>) {
  const result: Record<string, unknown> = { ...base }
  for (const [key, value] of Object.entries(extra)) {
    const existing = result[key]
    const bothObjects =
      value !== null &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      existing !== null &&
      typeof existing === "object" &&
      !Array.isArray(existing)
    result[key] = bothObjects
      ? merge(existing as Record<string, unknown>, value as Record<string, unknown>)
      : value
  }
  return result
}

/** Fonts, rules, margins and the legend position shared by every chart. */
function baseLayout(showLegend: boolean): Record<string, unknown> {
  const family = getComputedStyle(document.body).fontFamily
  const ink = token("chart-ink")
  const secondary = token("chart-ink-secondary")
  const muted = token("chart-muted")
  const grid = token("chart-grid")
  const axis = token("chart-axis")
  const title = { standoff: 12, font: { size: 12, color: muted } }
  return {
    autosize: true,
    font: { family, size: 12, color: secondary },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    margin: { l: 56, r: 16, t: showLegend ? 36 : 12, b: 36 },
    showlegend: showLegend,
    legend: { orientation: "h", x: 0, y: 1.02, yanchor: "bottom", font: { color: secondary } },
    hovermode: "x unified",
    hoverlabel: {
      bgcolor: token("chart-surface"),
      bordercolor: grid,
      font: { family, size: 12, color: ink },
    },
    bargap: 0.3,
    xaxis: {
      showgrid: false,
      zeroline: false,
      linecolor: axis,
      tickcolor: axis,
      ticks: "outside",
      ticklen: 4,
      automargin: true,
      hoverformat: "%B %Y",
      title,
    },
    yaxis: {
      gridcolor: grid,
      zeroline: false,
      automargin: true,
      tickformat: ",",
      title,
    },
  }
}

function themed(figure: Figure) {
  const resolved = resolveTokens(figure) as Figure
  const showLegend = resolved.layout.showlegend !== false
  return { data: resolved.data, layout: merge(baseLayout(showLegend), resolved.layout) }
}

export function Chart({
  figure,
  label,
  height = 320,
}: {
  figure: Figure
  /** What the chart shows, for people who cannot see it. */
  label: string
  height?: number
}) {
  const ref = React.useRef<HTMLDivElement>(null)
  const { theme } = useTheme()

  // Drawn again when the theme changes, because the colours are read from it.
  React.useEffect(() => {
    const element = ref.current
    if (!element) return
    let stale = false
    loadPlotly().then((Plotly) => {
      if (stale) return
      const { data, layout } = themed(figure)
      Plotly.react(element, data, layout, { displayModeBar: false, responsive: true })
    })
    return () => {
      stale = true
    }
  }, [figure, theme])

  React.useEffect(() => {
    const element = ref.current
    if (!element) return
    // The sidebar opening or closing resizes the chart without resizing the window.
    const observer = new ResizeObserver(() => {
      loadPlotly().then((Plotly) => {
        if (element.isConnected && element.classList.contains("js-plotly-plot")) {
          Plotly.Plots.resize(element)
        }
      })
    })
    observer.observe(element)
    return () => {
      observer.disconnect()
      loadPlotly().then((Plotly) => Plotly.purge(element))
    }
  }, [])

  return <div ref={ref} role="img" aria-label={label} className="w-full" style={{ height }} />
}
