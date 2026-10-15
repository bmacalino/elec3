import { ChartCard } from "@/components/chart-card"
import { Num, NumHead, TableCard } from "@/components/data-table"
import { StatCard } from "@/components/kpi-card"
import { PageBody } from "@/components/page-body"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useApi } from "@/lib/api"
import { decimal } from "@/lib/format"
import type { Seasonality } from "@/lib/types"

function strengthWord(strength: number): string {
  if (strength >= 0.64) return "Strong"
  if (strength >= 0.4) return "Moderate"
  return "Weak"
}

export function SeasonalityPage() {
  const state = useApi<Seasonality>("/api/seasonality")

  return (
    <PageBody state={state} needs={["monthly", "analysis"]}>
      {(data) => (
        <>
          <section aria-label="Summary" className="grid gap-4 sm:grid-cols-3">
            <StatCard
              title="Usually highest in"
              value={data.highest_months.join(", ")}
              caption="The three calendar months with the highest seasonal index"
            />
            <StatCard
              title="Usually lowest in"
              value={data.lowest_months.join(", ")}
              caption="The three calendar months with the lowest seasonal index"
            />
            <StatCard
              title="Seasonal pattern"
              value={strengthWord(data.strength)}
              caption={`Strength ${decimal(data.strength, 2)} on a scale from 0 (none) to 1, from the STL decomposition of ${data.study_period}`}
            />
          </section>

          <div className="grid gap-4 xl:grid-cols-2">
            <ChartCard chart={data.charts.index} height={300} />
            <ChartCard chart={data.charts.average} height={300} />
          </div>

          <Tabs defaultValue="relative">
            <TabsList>
              <TabsTrigger value="relative">Against the level of the time</TabsTrigger>
              <TabsTrigger value="level">In US dollars</TabsTrigger>
            </TabsList>
            <TabsContent value="relative">
              <ChartCard chart={data.charts.heatmap_relative} height={340} />
            </TabsContent>
            <TabsContent value="level">
              <ChartCard chart={data.charts.heatmap_level} height={340} />
            </TabsContent>
          </Tabs>

          <section aria-labelledby="decomposition-heading" className="flex flex-col gap-4">
            <div>
              <h2 id="decomposition-heading" className="text-base font-medium">
                Decomposition
              </h2>
              <p className="max-w-3xl text-sm text-muted-foreground">
                STL splits each month's remittances into three parts that add up to the observed
                value.
              </p>
            </div>
            <div className="grid gap-4 xl:grid-cols-3">
              {data.decomposition.map((chart) => (
                <ChartCard key={chart.key} chart={chart} height={240} />
              ))}
            </div>
          </section>

          <TableCard
            title="Calendar months"
            description={`Averages cover the complete years ${data.average_years[0]} to ${data.average_years[1]}. An index of 100 is an ordinary month.`}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Month</TableHead>
                  <NumHead>Average (US$ million)</NumHead>
                  <NumHead>Seasonal index</NumHead>
                  <NumHead>Rank</NumHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.profile.map((row) => (
                  <TableRow key={row.month}>
                    <TableCell>{row.label}</TableCell>
                    <Num>{decimal(row.average, 1)}</Num>
                    <Num>{decimal(row.seasonal_index, 1)}</Num>
                    <Num>{row.rank}</Num>
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
