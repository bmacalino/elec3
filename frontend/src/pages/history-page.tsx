import { Download } from "lucide-react"

import { ChartCard } from "@/components/chart-card"
import { Num, NumHead, TableCard } from "@/components/data-table"
import { MonthRangeFilter } from "@/components/month-range"
import { PageBody } from "@/components/page-body"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useApi, withQuery } from "@/lib/api"
import { decimal, monthLabel, signedPercent } from "@/lib/format"
import { useQueryParams } from "@/lib/query"
import type { History } from "@/lib/types"

export function HistoryPage() {
  const [query, setQuery] = useQueryParams(["start", "end"] as const)
  const state = useApi<History>(withQuery("/api/history", query))

  return (
    <PageBody state={state} needs={["monthly"]}>
      {(data) => {
        const range = {
          start: query.start ?? data.range.start,
          end: query.end ?? data.range.end,
        }
        return (
          <>
            <MonthRangeFilter
              min={data.range.min}
              max={data.range.max}
              value={range}
              onChange={setQuery}
            />

            <div className="grid gap-4 xl:grid-cols-2">
              {data.charts.map((chart) => (
                <ChartCard key={chart.key} chart={chart} height={280} />
              ))}
            </div>

            <TableCard
              title="Monthly values"
              description={`${data.range.label}, ${data.rows.length} months. Sources: Bangko Sentral ng Pilipinas (remittances, exchange rate) and Philippine Statistics Authority (inflation).`}
              scroll
              action={
                <Button asChild variant="outline" size="sm">
                  <a href={withQuery("/api/history.csv", range)} download>
                    <Download aria-hidden />
                    Download CSV
                  </a>
                </Button>
              }
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Month</TableHead>
                    <NumHead>Cash remittances (US$ million)</NumHead>
                    <NumHead>Change from a year earlier</NumHead>
                    <NumHead>Pesos per US$1</NumHead>
                    <NumHead>Change from a year earlier</NumHead>
                    <NumHead>Inflation rate</NumHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.rows.map((row) => (
                    <TableRow key={row.month}>
                      <TableCell>
                        {monthLabel(row.month)}
                        {row.preliminary && (
                          <span className="text-muted-foreground"> (preliminary)</span>
                        )}
                      </TableCell>
                      <Num>{decimal(row.cash, 1)}</Num>
                      <Num>{signedPercent(row.cash_yoy)}</Num>
                      <Num>{decimal(row.fx, 2)}</Num>
                      <Num>{signedPercent(row.fx_yoy)}</Num>
                      <Num>{decimal(row.inflation, 1)}%</Num>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableCard>
          </>
        )
      }}
    </PageBody>
  )
}
