import { Download } from "lucide-react"

import { ChartCard } from "@/components/chart-card"
import { Num, NumHead, TableCard } from "@/components/data-table"
import { StatCard } from "@/components/kpi-card"
import { PageBody } from "@/components/page-body"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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
import { decimal, monthLabel, percent, signedDecimal, signedPercent, usd } from "@/lib/format"
import { useQueryParams } from "@/lib/query"
import type { ModelRow, Models } from "@/lib/types"

function pValue(value: number): string {
  return value < 0.001 ? "< 0.001" : decimal(value, 3)
}

function list(names: string[]): string {
  if (names.length <= 1) return names.join("")
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`
}

function ruleCaption(data: Models): string {
  const { selection } = data
  const rule = `${selection.description}.`
  if (selection.agree) return `${rule} It is also the best on the latest window alone.`
  const other = selection.rule === "rolling" ? selection.best_on_test : selection.best_on_rolling
  const where = selection.rule === "rolling" ? "on the latest window alone" : "on the average of all windows"
  return `${rule} ${other} is ahead ${where}.`
}

function difference(row: ModelRow) {
  if (row.is_best) return <Badge>Main model</Badge>
  if (row.different === null) return null
  return (
    <Badge variant="outline">{row.different ? "Less accurate" : "Cannot be told apart"}</Badge>
  )
}

export function ModelsPage() {
  const [query, setQuery] = useQueryParams(["model"] as const)
  const state = useApi<Models>(withQuery("/api/models", query))

  return (
    <PageBody state={state} needs={["metrics"]}>
      {(data) => {
        const selected = data.models.find((row) => row.key === data.selected)
        const tied = data.selection.not_different
        return (
          <>
            <section aria-label="Summary" className="grid gap-4 sm:grid-cols-3">
              <StatCard title="Main model" value={data.best.name} caption={ruleCaption(data)} />
              <StatCard
                title="Its average error"
                value={`${usd(data.best.rolling_rmse)} RMSE`}
                caption={`Over ${data.selection.windows} twelve-month test windows. On the latest, ${data.split.test}: ${usd(data.best.rmse)} RMSE, ${percent(data.best.mape, 2)} away from the actual value on average.`}
              />
              <StatCard
                title="Cannot be told apart from it"
                value={tied.length > 0 ? list(tied) : "No other model"}
                caption={`A Diebold–Mariano test on the ${data.selection.forecasts_compared} monthly forecasts in the test windows cannot rule out that the difference is chance. A model whose errors swing widely between windows can appear here even with a higher average error. The other models are less accurate by more than chance.`}
              />
            </section>

            <ChartCard chart={data.charts.rmse} height={360} />

            <TableCard
              title="Error of every model"
              description={`US$ million; lower is better. The first number column is the average over the ${data.selection.windows} test windows and decides the main model. MAE, RMSE and MAPE are for the latest window, ${data.split.test}. The p-value tests whether a model's errors differ from the main model's; below 0.05 they do.`}
              action={
                <Button asChild variant="outline" size="sm">
                  <a href="/api/models.csv" download>
                    <Download aria-hidden />
                    Download CSV
                  </a>
                </Button>
              }
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Model</TableHead>
                    <NumHead>Average RMSE</NumHead>
                    <NumHead>MAE</NumHead>
                    <NumHead>RMSE</NumHead>
                    <NumHead>MAPE</NumHead>
                    <NumHead>P-value</NumHead>
                    <TableHead>Against the main model</TableHead>
                    <NumHead>Test months inside the 95% interval</NumHead>
                    <TableHead>Settings chosen on the training months</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.models.map((row) => (
                    <TableRow key={row.key}>
                      <TableCell>
                        <span className="flex flex-wrap items-center gap-2">
                          {row.name}
                          {!row.candidate && <Badge variant="outline">Reference only</Badge>}
                        </span>
                      </TableCell>
                      <Num className={row.is_best ? "font-medium" : ""}>
                        {decimal(row.rolling_rmse, 1)}
                      </Num>
                      <Num>{decimal(row.mae, 1)}</Num>
                      <Num>{decimal(row.rmse, 1)}</Num>
                      <Num>{percent(row.mape, 2)}</Num>
                      <Num>{row.p_value === null ? "" : pValue(row.p_value)}</Num>
                      <TableCell>{difference(row)}</TableCell>
                      <Num>
                        {row.coverage ? `${row.coverage.inside} of ${row.coverage.months}` : ""}
                      </Num>
                      <TableCell className="text-muted-foreground">{row.spec}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableCard>

            <TableCard
              title="Error in each test window"
              description="RMSE in US$ million. Each column is the last month of data the models were given; they then forecast the next 12 months. Settings were chosen again for every window, using only the months up to it."
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Model</TableHead>
                    {data.rolling.origins.map((origin) => (
                      <NumHead key={origin}>{monthLabel(origin)}</NumHead>
                    ))}
                    <NumHead>Average</NumHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.rolling.rows.map((row) => (
                    <TableRow key={row.key}>
                      <TableCell>{row.name}</TableCell>
                      {row.rmse.map((value, index) => (
                        <Num key={data.rolling.origins[index]}>{decimal(value, 1)}</Num>
                      ))}
                      <Num className="font-medium">{decimal(row.mean, 1)}</Num>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableCard>

            <section aria-labelledby="predicted-heading" className="flex flex-col gap-4">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <h2 id="predicted-heading" className="text-base font-medium">
                    Actual against predicted, month by month
                  </h2>
                  <p className="max-w-3xl text-sm text-muted-foreground">
                    The latest test window, {data.split.test}. The models were built on{" "}
                    {data.split.train} ({data.split.train_months} months) and never saw these{" "}
                    {data.split.test_months} months.
                  </p>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="model">Model</Label>
                  <Select value={data.selected} onValueChange={(model) => setQuery({ model })}>
                    <SelectTrigger id="model" className="w-64">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {data.models.map((row) => (
                        <SelectItem key={row.key} value={row.key}>
                          {row.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <ChartCard chart={data.charts.actual_vs_predicted} height={340}>
                {selected?.interval_method === "backtest" && (
                  <p className="text-sm text-muted-foreground">
                    The shaded interval is the size that would have contained 95% of this model's
                    errors in {data.interval_backtests} earlier forecasts, all made before the
                    test months.
                  </p>
                )}
              </ChartCard>
              <TableCard
                title={`Predictions of ${selected?.name ?? "the selected model"}`}
                description="US$ million. Every prediction was made from the training months alone, before any of these months were known."
              >
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Month</TableHead>
                      <NumHead>Actual</NumHead>
                      <NumHead>Predicted</NumHead>
                      <NumHead>Error</NumHead>
                      <NumHead>Error, percent</NumHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.predictions.map((row) => (
                      <TableRow key={row.month}>
                        <TableCell>{monthLabel(row.month)}</TableCell>
                        <Num>{decimal(row.actual, 1)}</Num>
                        <Num>{decimal(row.predicted, 1)}</Num>
                        <Num>{signedDecimal(row.error)}</Num>
                        <Num>{signedPercent(row.error_pct, 2)}</Num>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableCard>
            </section>

            <TableCard
              title="Indicator models: fair test against a test with hindsight"
              description="RMSE in US$ million on the latest window. In the fair test the exchange rate and inflation stay at their values in the last training month, as they would for a real forecast. The hindsight column gives the models the values that later occurred; it is shown for comparison only."
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Model</TableHead>
                    <NumHead>Fair test</NumHead>
                    <NumHead>With hindsight</NumHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.with_actual_indicators.map((row) => (
                    <TableRow key={row.name}>
                      <TableCell>{row.name}</TableCell>
                      <Num>{decimal(row.rmse_held, 1)}</Num>
                      <Num>{decimal(row.rmse_actual, 1)}</Num>
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
