import type { ReactNode } from "react"

import { Chart } from "@/components/chart"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { ChartBlock } from "@/lib/types"

/** A chart inside a card, with its title and what the numbers are. */
export function ChartCard({
  chart,
  height,
  children,
}: {
  chart: ChartBlock
  height?: number
  /** Shown under the chart: a legend or a note. */
  children?: ReactNode
}) {
  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>{chart.title}</CardTitle>
        <CardDescription>{chart.subtitle}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Chart figure={chart.figure} label={`${chart.title}. ${chart.subtitle}`} height={height} />
        {children}
      </CardContent>
    </Card>
  )
}
