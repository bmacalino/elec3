import { Info } from "lucide-react"

import { Chart } from "@/components/chart"
import { ChartCard } from "@/components/chart-card"
import { Num, NumHead, TableCard } from "@/components/data-table"
import { PageBody } from "@/components/page-body"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useApi } from "@/lib/api"
import { decimal, percent, signedPercent } from "@/lib/format"
import type { Relationships } from "@/lib/types"

type Indicator = Relationships["indicators"][number]

function pValue(value: number): string {
  return value < 0.001 ? "< 0.001" : decimal(value, 3)
}

/** The KPSS p-value is only tabulated between 0.01 and 0.10. */
function kpssPValue(value: number): string {
  if (value <= 0.01) return "0.01 or less"
  if (value >= 0.1) return "0.10 or more"
  return decimal(value, 3)
}

const VERDICTS = {
  stationary: "Stationary",
  "not stationary": "Not stationary",
  "tests disagree": "The tests disagree",
}

function Verdict({ yes, yesText, noText }: { yes: boolean; yesText: string; noText: string }) {
  return <Badge variant={yes ? "default" : "outline"}>{yes ? yesText : noText}</Badge>
}

function correlationSentence(item: Indicator): string {
  const strongest = `The strongest correlation is ${decimal(item.strongest_correlation, 2)}, with the indicator ${item.strongest_lag} months earlier`
  if (item.significant_lags.length === 0) {
    return `${strongest}. No lag from 0 to 12 months is statistically significant.`
  }
  const lags = item.significant_lags.join(", ")
  return `${strongest}. Significant at ${item.significant_lags.length === 1 ? "lag" : "lags"} ${lags}; with 13 lags tested, one significant result can occur by chance.`
}

function grangerSentence(item: Indicator): string {
  if (item.granger_significant_lags.length === 0) {
    return "Granger test: past values of this indicator do not help predict remittances, at any of 1 to 6 lags."
  }
  return `Granger test: past values of this indicator help predict remittances when ${item.granger_significant_lags.join(", ")} lags are included.`
}

export function RelationshipsPage() {
  const state = useApi<Relationships>("/api/relationships")

  return (
    <PageBody state={state} needs={["monthly", "analysis", "metrics"]}>
      {(data) => (
        <>
          <Alert className="max-w-3xl">
            <Info />
            <AlertTitle>These results show association, not cause</AlertTitle>
            <AlertDescription>
              The tests show whether remittances move together with the exchange rate and
              inflation, and whether those indicators help predict remittances. They do not show
              that one causes the other. Period: {data.study_period}.
            </AlertDescription>
          </Alert>

          <section aria-labelledby="series-heading" className="flex flex-col gap-4">
            <h2 id="series-heading" className="text-base font-medium">
              The three series on the same year-on-year basis
            </h2>
            <div className="grid gap-4 xl:grid-cols-3">
              {data.series.map((chart) => (
                <ChartCard key={chart.key} chart={chart} height={240} />
              ))}
            </div>
          </section>

          <section aria-labelledby="lags-heading" className="flex flex-col gap-4">
            <div>
              <h2 id="lags-heading" className="text-base font-medium">
                Does the indicator lead remittances, and by how many months?
              </h2>
              <p className="max-w-3xl text-sm text-muted-foreground">
                Each bar is the correlation between the year-on-year change in remittances and the
                indicator that many months earlier. Bars beyond the dotted lines are statistically
                significant at the {percent(data.significance * 100, 0)} level and are shown in
                colour.
              </p>
            </div>
            <div className="grid gap-4 xl:grid-cols-3">
              {data.indicators.map((item) => (
                <Card key={item.key}>
                  <CardHeader>
                    <CardTitle>{item.label}</CardTitle>
                    <CardDescription>
                      {item.differenced
                        ? "Month-to-month change of the series, because the series itself is not stationary"
                        : "The series as it is"}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-3">
                    <Chart
                      figure={item.figure}
                      label={`Correlation of remittances with ${item.label} at lags 0 to 12 months`}
                      height={240}
                    />
                    <p className="text-sm">{correlationSentence(item)}</p>
                    <p className="text-sm">{grangerSentence(item)}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>

          <TableCard
            title="Granger causality tests"
            description="P-value of the test that the indicator's past adds nothing to a forecast from remittances' own past. Below 0.05, the indicator helps."
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Indicator</TableHead>
                  {data.indicators[0].granger.map((test) => (
                    <NumHead key={test.lags}>
                      {test.lags} {test.lags === 1 ? "lag" : "lags"}
                    </NumHead>
                  ))}
                  <TableHead>Helps predict</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.indicators.map((item) => (
                  <TableRow key={item.key}>
                    <TableCell>{item.label}</TableCell>
                    {item.granger.map((test) => (
                      <Num key={test.lags} className={test.significant ? "font-medium" : ""}>
                        {pValue(test.p_value)}
                      </Num>
                    ))}
                    <TableCell>
                      <Verdict
                        yes={item.granger_significant_lags.length > 0}
                        yesText="Yes"
                        noText="No"
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableCard>

          <TableCard
            title="Do the results hold under other choices?"
            description={`Two checks. First, remittances fell and rebounded sharply in 2020 and 2021, which could hide a real link, so the tests are repeated on ${data.sensitivity.recent_period} (${data.sensitivity.recent_months} months). Second, the two stationarity tests disagree about ${data.sensitivity.disputed.length} of the indicators, so for those the tests are repeated without differencing. ${
              data.sensitivity.same_conclusion
                ? "The Granger tests reach the same conclusion every time."
                : "The Granger tests do not reach the same conclusion every time, so the result depends on these choices."
            }`}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Indicator</TableHead>
                  <TableHead>Tested on</TableHead>
                  <NumHead>Strongest correlation</NumHead>
                  <NumHead>At lag (months)</NumHead>
                  <TableHead>Significant lags</TableHead>
                  <NumHead>Lowest Granger p-value</NumHead>
                  <TableHead>Helps predict</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.sensitivity.rows.flatMap((row) =>
                  row.results.map((result) => (
                    <TableRow key={`${row.label}-${result.key}`}>
                      <TableCell>{row.label}</TableCell>
                      <TableCell>{result.label}</TableCell>
                      <Num>{decimal(result.strongest_correlation, 2)}</Num>
                      <Num>{result.strongest_lag}</Num>
                      <TableCell>
                        {result.significant_lags.length > 0
                          ? result.significant_lags.join(", ")
                          : "None"}
                      </TableCell>
                      <Num>{pValue(result.granger_lowest_p)}</Num>
                      <TableCell>
                        <Verdict
                          yes={result.granger_significant_lags.length > 0}
                          yesText="Yes"
                          noText="No"
                        />
                      </TableCell>
                    </TableRow>
                  )),
                )}
              </TableBody>
            </Table>
          </TableCard>

          <section aria-labelledby="models-heading" className="flex flex-col gap-4">
            <div>
              <h2 id="models-heading" className="text-base font-medium">
                What the forecasting models say
              </h2>
              <p className="max-w-3xl text-sm text-muted-foreground">
                The indicators enter the models with a lag of at least {data.indicator_lag} months.
              </p>
            </div>

            <TableCard
              title="Do the indicators improve the forecasts?"
              description={`RMSE in US$ million of each model without and with the exchange rate and inflation, averaged over the ${data.rolling_windows} test windows. Lower is better. The last two columns show the most recent window alone.`}
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Model</TableHead>
                    <NumHead>Without indicators</NumHead>
                    <NumHead>With indicators</NumHead>
                    <NumHead>Change in error</NumHead>
                    <TableHead>Result</TableHead>
                    <NumHead>Latest window, without</NumHead>
                    <NumHead>Latest window, with</NumHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.effect.map((row) => (
                    <TableRow key={row.without}>
                      <TableCell>
                        {row.without} and {row.with}
                      </TableCell>
                      <Num>{decimal(row.rolling_without, 1)}</Num>
                      <Num>{decimal(row.rolling_with, 1)}</Num>
                      <Num>{signedPercent(row.rolling_change_pct)}</Num>
                      <TableCell>
                        <Verdict
                          yes={row.improves_rolling}
                          yesText="Lower error"
                          noText="Higher error"
                        />
                      </TableCell>
                      <Num>{decimal(row.rmse_without, 1)}</Num>
                      <Num>{decimal(row.rmse_with, 1)}</Num>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableCard>

            <div className="grid gap-4 xl:grid-cols-2">
              {data.importance.map((item) => (
                <Card key={item.key}>
                  <CardHeader>
                    <CardTitle>Feature importance: {item.model}</CardTitle>
                    <CardDescription>
                      The exchange rate and inflation features carry{" "}
                      {percent(item.indicator_share, 0)} of the importance.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-3">
                    <Chart
                      figure={item.figure}
                      label={`Feature importance of ${item.model}`}
                      height={360}
                    />
                    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
                      <li className="flex items-center gap-1.5">
                        <span className="size-3 rounded-sm bg-chart-1" aria-hidden />
                        Past remittances and calendar month
                      </li>
                      <li className="flex items-center gap-1.5">
                        <span className="size-3 rounded-sm bg-chart-2" aria-hidden />
                        Exchange rate and inflation
                      </li>
                    </ul>
                  </CardContent>
                </Card>
              ))}
            </div>

            <TableCard
              title="Coefficients in ARIMAX and SARIMAX"
              description="Estimated effect on monthly remittances, in US$ million, of a one-point rise in the indicator. A p-value below 0.05 means the effect is distinguishable from zero."
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Model</TableHead>
                    <TableHead>Indicator</TableHead>
                    <NumHead>Coefficient</NumHead>
                    <NumHead>P-value</NumHead>
                    <TableHead>Significant</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.coefficients.map((row) => (
                    <TableRow key={`${row.model}-${row.term}`}>
                      <TableCell>{row.model}</TableCell>
                      <TableCell>{row.term}</TableCell>
                      <Num>{decimal(row.coefficient, 2)}</Num>
                      <Num>{pValue(row.p_value)}</Num>
                      <TableCell>
                        <Verdict yes={row.significant} yesText="Yes" noText="No" />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableCard>
          </section>

          <TableCard
            title="Stationarity tests"
            description={`Two tests that ask opposite questions. ADF: a p-value below 0.05 means the series is stationary. KPSS: a p-value below 0.05 means it is not. The ADF test decides which form of each series is used; KPSS is a second opinion. The two indicators have a correlation of ${decimal(data.overlap.correlation, 2)} with each other (variance inflation factor ${decimal(data.overlap.variance_inflation_factor, 2)}), low enough to use both in one model.`}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Series</TableHead>
                  <TableHead>Form</TableHead>
                  <NumHead>ADF p-value</NumHead>
                  <NumHead>KPSS p-value</NumHead>
                  <TableHead>Together</TableHead>
                  <TableHead>Used in the tests above</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.stationarity.flatMap((row) =>
                  (
                    [
                      ["As it is", row.level, row.differencing === 0],
                      ["Month-to-month change", row.first_difference, row.differencing === 1],
                    ] as const
                  ).map(([form, result, used]) => (
                    <TableRow key={`${row.series}-${form}`}>
                      <TableCell>{row.label}</TableCell>
                      <TableCell>{form}</TableCell>
                      <Num>{pValue(result.adf.p_value)}</Num>
                      <Num>{kpssPValue(result.kpss.p_value)}</Num>
                      <TableCell>{VERDICTS[result.verdict]}</TableCell>
                      <TableCell>{used ? "Yes" : ""}</TableCell>
                    </TableRow>
                  )),
                )}
              </TableBody>
            </Table>
          </TableCard>
        </>
      )}
    </PageBody>
  )
}
