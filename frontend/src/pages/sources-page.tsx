import { ChartCard } from "@/components/chart-card"
import { Num, NumHead, TableCard } from "@/components/data-table"
import { PageBody } from "@/components/page-body"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useApi, withQuery } from "@/lib/api"
import { decimal, percent, signedPercent } from "@/lib/format"
import { useQueryParams } from "@/lib/query"
import type { Sources } from "@/lib/types"

export function SourcesPage() {
  const [query, setQuery] = useQueryParams(["year"] as const)
  const state = useApi<Sources>(withQuery("/api/sources", query))

  return (
    <PageBody state={state} needs={["by_source", "by_country"]}>
      {(data) => (
        <>
          <section aria-labelledby="source-heading" className="flex flex-col gap-4">
            <h2 id="source-heading" className="text-base font-medium">
              By type of worker
            </h2>
            <ChartCard chart={data.charts.source} height={320} />
            <TableCard
              title="Yearly totals by type of worker"
              description="US$ million. Sea-based workers are seafarers; all others are land-based."
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Year</TableHead>
                    <NumHead>Land-based</NumHead>
                    <NumHead>Sea-based</NumHead>
                    <NumHead>Total</NumHead>
                    <NumHead>Sea-based share</NumHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.yearly.map((row) => (
                    <TableRow key={row.year}>
                      <TableCell>{row.label}</TableCell>
                      <Num>{decimal(row.land_based, 1)}</Num>
                      <Num>{decimal(row.sea_based, 1)}</Num>
                      <Num>{decimal(row.total, 1)}</Num>
                      <Num>{percent(row.sea_share)}</Num>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableCard>
          </section>

          <section aria-labelledby="country-heading" className="flex flex-col gap-4">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 id="country-heading" className="text-base font-medium">
                  By country of origin
                </h2>
                <p className="max-w-3xl text-sm text-muted-foreground">
                  Banks record the country the money was sent through. Remittances routed through
                  correspondent banks, many of them in the United States, are counted there, so
                  that country's share is overstated.
                </p>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="year">Year</Label>
                <Select
                  value={query.year ?? String(data.year)}
                  onValueChange={(year) => setQuery({ year })}
                >
                  <SelectTrigger id="year" className="w-44">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {data.years.map((option) => (
                      <SelectItem key={option.year} value={String(option.year)}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <ChartCard chart={data.charts.top} height={380} />
              <ChartCard chart={data.charts.growth} height={380} />
            </div>

            <TableCard
              title={`Fifteen largest sources, ${data.period}`}
              description={`US$ million. ${data.country_count} countries and territories sent remittances in this period. Each change compares with the same months of ${data.year - 1}. Country names follow the list the Bangko Sentral ng Pilipinas adopted in July 2023; earlier figures are matched to those names.`}
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <NumHead>Rank</NumHead>
                    <TableHead>Country</TableHead>
                    <NumHead>Total</NumHead>
                    <NumHead>Share of all remittances</NumHead>
                    <NumHead>Land-based</NumHead>
                    <NumHead>Sea-based</NumHead>
                    <NumHead>Change from the year before</NumHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.countries.map((row) => (
                    <TableRow key={row.country}>
                      <Num>{row.rank}</Num>
                      <TableCell>{row.country}</TableCell>
                      <Num>{decimal(row.total, 1)}</Num>
                      <Num>{percent(row.share)}</Num>
                      <Num>{decimal(row.land_based, 1)}</Num>
                      <Num>{decimal(row.sea_based, 1)}</Num>
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
          </section>
        </>
      )}
    </PageBody>
  )
}
