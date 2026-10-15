import { ChartCard } from "@/components/chart-card"
import { Num, NumHead, TableCard } from "@/components/data-table"
import { StatCard } from "@/components/kpi-card"
import { MonthRangeFilter } from "@/components/month-range"
import { PageBody } from "@/components/page-body"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useApi, withQuery } from "@/lib/api"
import { decimal, monthLabel, percent, signedPercent, usd } from "@/lib/format"
import { useQueryParams } from "@/lib/query"
import type { Trends } from "@/lib/types"

const DIRECTION = { rising: "Rising", falling: "Falling", stable: "Stable" }

function directionCaption(data: Trends): string {
  const { direction, annual_change_pct, from, to } = data.direction
  if (!direction || annual_change_pct === null || !from || !to) {
    return "The 12-month average needs at least two months in the selected period, and starts in December 2019."
  }
  const size = percent(Math.abs(annual_change_pct))
  const move =
    direction === "stable"
      ? `changed by ${size} a year, within the ${percent(data.stable_band_pct, 0)} band counted as stable`
      : `${direction === "rising" ? "rose" : "fell"} by ${size} a year`
  return `The 12-month average ${move}, ${monthLabel(from)} to ${monthLabel(to)}.`
}

export function TrendsPage() {
  const [query, setQuery] = useQueryParams(["start", "end"] as const)
  const state = useApi<Trends>(withQuery("/api/trends", query))

  return (
    <PageBody state={state} needs={["monthly"]}>
      {(data) => (
        <>
          <MonthRangeFilter
            min={data.range.min}
            max={data.range.max}
            value={{
              start: query.start ?? data.range.start,
              end: query.end ?? data.range.end,
            }}
            onChange={setQuery}
          />

          <section aria-label="Summary" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              title="Direction"
              value={data.direction.direction ? DIRECTION[data.direction.direction] : "Not available"}
              caption={directionCaption(data)}
            />
            <StatCard
              title="Total"
              value={usd(data.summary.total)}
              caption={`${data.range.label}, ${data.summary.months} months`}
            />
            <StatCard
              title="Average per month"
              value={usd(data.summary.average)}
              caption={`Highest in ${monthLabel(data.summary.highest_month)}, lowest in ${monthLabel(data.summary.lowest_month)}`}
            />
            <StatCard
              title="First month to last month"
              value={signedPercent(data.summary.change_pct)}
              caption={`${usd(data.summary.first)} in ${monthLabel(data.range.start)}, ${usd(data.summary.last)} in ${monthLabel(data.range.end)}`}
            />
          </section>

          <ChartCard chart={data.charts.moving_averages} height={360} />
          <ChartCard chart={data.charts.change} height={280} />

          <TableCard
            title="Yearly totals"
            description="All years in the study period. Each change compares with the same months of the year before."
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Year</TableHead>
                  <NumHead>Total (US$ million)</NumHead>
                  <NumHead>Average per month (US$ million)</NumHead>
                  <NumHead>Change from the year before</NumHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.annual.map((row) => (
                  <TableRow key={row.year}>
                    <TableCell>{row.label}</TableCell>
                    <Num>{decimal(row.total, 1)}</Num>
                    <Num>{decimal(row.average, 1)}</Num>
                    <Num>
                      {row.change_pct === null ? (
                        <span className="text-muted-foreground">No earlier year</span>
                      ) : (
                        signedPercent(row.change_pct)
                      )}
                    </Num>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableCard>
        </>
      )}
    </PageBody>
  )
}
