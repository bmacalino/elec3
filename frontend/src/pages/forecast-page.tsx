import * as React from "react"
import { Download, Info } from "lucide-react"

import { ChartCard } from "@/components/chart-card"
import { Num, NumHead, TableCard } from "@/components/data-table"
import { StatCard } from "@/components/kpi-card"
import { PageBody } from "@/components/page-body"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
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
import { decimal, monthLabel, percent, peso, signedDecimal, signedPercent, usd } from "@/lib/format"
import { useQueryParams } from "@/lib/query"
import type { Forecast } from "@/lib/types"

const FILTERS = ["model", "horizon", "exchange_rate", "inflation"] as const

function trainedRange(data: Forecast): string {
  const range = data.assumptions.range
  if (!range) return ""
  const [lowChange, highChange] = range.exchange_rate_change.trained
  const [lowPrice, highPrice] = range.inflation.trained
  return `It was fitted on inflation between ${percent(lowPrice)} and ${percent(highPrice)}, and on a peso–dollar rate between ${signedPercent(lowChange)} and ${signedPercent(highChange)} from a year earlier.`
}

function assumptionNote(data: Forecast): { title: string; text: string } | null {
  const { assumptions, model } = data
  if (!model.uses_indicators) {
    if (!assumptions.custom) return null
    return {
      title: "The assumed values do not affect this model",
      text: `${model.name} forecasts from past remittances only. Choose a model with indicators (ARIMAX, SARIMAX, or Random Forest or XGBoost with indicators) to see the effect.`,
    }
  }
  const range = assumptions.range
  const outside = range && (range.exchange_rate_change.outside || range.inflation.outside)
  const isTree = model.family === "machine learning"
  if (assumptions.custom && outside) {
    return {
      title: "The assumed values are outside what this model was fitted on",
      text: `${trainedRange(data)} ${
        isTree
          ? `${model.name} is built from decision trees, which give the same forecast beyond that range as at its edge.`
          : `Beyond that range ${model.name} extends the same straight-line relationship, which the data cannot confirm.`
      }`,
    }
  }
  if (assumptions.custom && !assumptions.changed_forecast) {
    return {
      title: "The assumed values did not change this forecast",
      text: `${model.name} is built from decision trees, which change their forecast only when an input crosses one of the values they split on. ${trainedRange(data)}`,
    }
  }
  return {
    title: `The first ${assumptions.indicator_lag} months do not depend on the assumptions`,
    text: `${model.name} uses the exchange rate and inflation from at least ${assumptions.indicator_lag} months earlier, so the first ${assumptions.indicator_lag} months rely on values already observed. Later months use the assumed values, held constant. ${trainedRange(data)}`,
  }
}

function intervalNote(data: Forecast): string {
  if (!data.model.has_intervals) {
    return `US$ million. ${data.model.name} has no prediction interval.`
  }
  if (data.model.interval_method === "backtest") {
    return `US$ million. The interval is the size that would have contained 95% of this model's errors in ${data.interval_backtests} earlier forecasts. It reflects the accuracy of recent years; a shock like the one in 2020 would fall outside it.`
  }
  return "US$ million. The interval is the range the model expects the value to fall in 95 times out of 100, from its own estimate of its error."
}

export function ForecastPage() {
  const [query, setQuery] = useQueryParams(FILTERS)
  // The two inputs are applied together, on submit, not on every keystroke.
  const [rate, setRate] = React.useState(query.exchange_rate ?? "")
  const [inflation, setInflation] = React.useState(query.inflation ?? "")
  const state = useApi<Forecast>(withQuery("/api/forecast", query))

  return (
    <PageBody state={state} needs={["monthly", "metrics", "forecasts"]}>
      {(data) => {
        const note = assumptionNote(data)
        const hasIntervals = data.model.has_intervals
        return (
          <>
            <Card>
              <CardHeader>
                <CardTitle>Forecast settings</CardTitle>
                <CardDescription>
                  Data to {data.last_observed}. Leave the two assumptions empty to keep the last
                  observed values: {peso(data.assumptions.exchange_rate.default)} per US dollar and{" "}
                  {percent(data.assumptions.inflation.default)} inflation.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form
                  className="flex flex-wrap items-end gap-4"
                  onSubmit={(event) => {
                    event.preventDefault()
                    setQuery({ exchange_rate: rate.trim(), inflation: inflation.trim() })
                  }}
                >
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="model">Model</Label>
                    <Select value={data.model.key} onValueChange={(model) => setQuery({ model })}>
                      <SelectTrigger id="model" className="w-64">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {data.options.models.map((option) => (
                          <SelectItem key={option.key} value={option.key}>
                            {option.name}
                            {option.is_main ? " (main model)" : ""}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="horizon">Months ahead</Label>
                    <Select
                      value={String(data.horizon)}
                      onValueChange={(horizon) => setQuery({ horizon })}
                    >
                      <SelectTrigger id="horizon" className="w-28">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {data.options.horizons.map((option) => (
                          <SelectItem key={option} value={String(option)}>
                            {option} months
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="rate">Assumed pesos per US$1</Label>
                    <Input
                      id="rate"
                      className="w-44"
                      inputMode="decimal"
                      placeholder={decimal(data.assumptions.exchange_rate.default, 2)}
                      value={rate}
                      onChange={(event) => setRate(event.target.value)}
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="inflation">Assumed inflation rate (%)</Label>
                    <Input
                      id="inflation"
                      className="w-44"
                      inputMode="decimal"
                      placeholder={decimal(data.assumptions.inflation.default, 1)}
                      value={inflation}
                      onChange={(event) => setInflation(event.target.value)}
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button type="submit">Apply assumptions</Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setRate("")
                        setInflation("")
                        setQuery({ exchange_rate: null, inflation: null })
                      }}
                    >
                      Clear
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>

            {note && (
              <Alert className="max-w-3xl">
                <Info />
                <AlertTitle>{note.title}</AlertTitle>
                <AlertDescription>{note.text}</AlertDescription>
              </Alert>
            )}

            <section aria-label="Summary" className="grid gap-4 sm:grid-cols-3">
              <StatCard
                title="Forecast total"
                value={usd(data.total.forecast)}
                caption={`${data.period}, ${data.model.name}`}
              />
              <StatCard
                title="Against the same months a year earlier"
                value={data.total.change_pct === null ? "Not available" : signedPercent(data.total.change_pct)}
                caption={`${usd(data.total.last_year)} was received in those months`}
              />
              <StatCard
                title={`First month, ${monthLabel(data.rows[0].month)}`}
                value={usd(data.rows[0].forecast)}
                caption={
                  data.assumptions.custom
                    ? `Assuming ${peso(data.assumptions.exchange_rate.used)} per US dollar and ${percent(data.assumptions.inflation.used)} inflation`
                    : "Exchange rate and inflation held at their last observed values"
                }
              />
            </section>

            <ChartCard chart={data.chart} height={380} />

            <TableCard
              title="Forecast by month"
              description={intervalNote(data)}
              action={
                <Button asChild variant="outline" size="sm">
                  <a href={withQuery("/api/forecast.csv", query)} download>
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
                    <NumHead>Forecast</NumHead>
                    {hasIntervals && <NumHead>95% interval</NumHead>}
                    <NumHead>Same month a year earlier</NumHead>
                    <NumHead>Change</NumHead>
                    {data.assumptions.custom && <NumHead>Effect of the assumptions</NumHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.rows.map((row) => (
                    <TableRow key={row.month}>
                      <TableCell>{monthLabel(row.month)}</TableCell>
                      <Num>{decimal(row.forecast, 1)}</Num>
                      {hasIntervals && (
                        <Num>
                          {row.lower !== null && row.upper !== null
                            ? `${decimal(row.lower, 1)} to ${decimal(row.upper, 1)}`
                            : ""}
                        </Num>
                      )}
                      <Num>{row.last_year === null ? "" : decimal(row.last_year, 1)}</Num>
                      <Num>{row.change_pct === null ? "" : signedPercent(row.change_pct)}</Num>
                      {data.assumptions.custom && <Num>{signedDecimal(row.difference)}</Num>}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableCard>

            <TableCard
              title={`How the models compare for ${data.period}`}
              description={`Forecast total of every model for the same months, with the exchange rate and inflation held at their last observed values. Models are listed from the lowest to the highest error ${
                data.comparison_error === "rolling"
                  ? "averaged over the test windows"
                  : "on the test months"
              }. Where the totals differ widely, the forecast is less certain.`}
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Model</TableHead>
                    <NumHead>Forecast total (US$ million)</NumHead>
                    <NumHead>Against the same months a year earlier</NumHead>
                    <NumHead>
                      {data.comparison_error === "rolling" ? "Average RMSE in testing" : "RMSE on the test months"}
                    </NumHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.comparison.map((row) => (
                    <TableRow key={row.key}>
                      <TableCell>
                        <span className="flex flex-wrap items-center gap-2">
                          {row.name}
                          {row.is_main && <Badge>Main model</Badge>}
                        </span>
                      </TableCell>
                      <Num>{decimal(row.total, 1)}</Num>
                      <Num>{row.change_pct === null ? "" : signedPercent(row.change_pct)}</Num>
                      <Num>{decimal(row.error, 1)}</Num>
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
