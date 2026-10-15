import { Minus, TrendingDown, TrendingUp } from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  percent,
  peso,
  signedPercent,
  signedPoints,
  signedUsd,
  usd,
} from "@/lib/format"
import type { Delta, Kpi } from "@/lib/types"

function formatValue(kpi: Kpi): string {
  switch (kpi.unit) {
    case "usd_million":
      return usd(kpi.value)
    case "percent_change":
      return signedPercent(kpi.value)
    case "percent":
      return percent(kpi.value)
    case "peso":
      return peso(kpi.value)
  }
}

function formatDelta(delta: Delta): string {
  switch (delta.unit) {
    case "percent":
      return signedPercent(delta.value)
    case "usd_million":
      return signedUsd(delta.value)
    case "points":
      return signedPoints(delta.value)
  }
}

const ICONS = { up: TrendingUp, down: TrendingDown, flat: Minus }
const DIRECTION_WORD = { up: "Up", down: "Down", flat: "No change" }
const TONES = {
  good: "text-(--delta-good)",
  bad: "text-(--delta-bad)",
  neutral: "text-muted-foreground",
}

export function DeltaLine({ delta }: { delta: Delta }) {
  const Icon = ICONS[delta.direction]
  return (
    <p className="flex flex-wrap items-center gap-x-1.5 text-sm">
      <span className={`inline-flex items-center gap-1 font-medium ${TONES[delta.tone]}`}>
        <Icon className="size-4" aria-hidden />
        <span className="sr-only">{DIRECTION_WORD[delta.direction]}:</span>
        {formatDelta(delta)}
      </span>
      <span className="text-muted-foreground">{delta.text}</span>
    </p>
  )
}

export function KpiCard({ kpi }: { kpi: Kpi }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>{kpi.title}</CardDescription>
        <CardTitle className="text-2xl font-semibold">{formatValue(kpi)}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-1">
        <DeltaLine delta={kpi.delta} />
        {kpi.range && (
          <p className="text-sm text-muted-foreground">
            Likely between {usd(kpi.range.lower)} and {usd(kpi.range.upper)}
          </p>
        )}
        <p className="text-xs text-muted-foreground">{kpi.caption}</p>
      </CardContent>
    </Card>
  )
}

/** A plain figure with a label, for summaries that have no comparison. */
export function StatCard({
  title,
  value,
  caption,
}: {
  title: string
  value: string
  caption?: string
}) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>{title}</CardDescription>
        <CardTitle className="text-2xl font-semibold">{value}</CardTitle>
      </CardHeader>
      {caption && (
        <CardContent>
          <p className="text-xs text-muted-foreground">{caption}</p>
        </CardContent>
      )}
    </Card>
  )
}
