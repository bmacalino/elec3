import { ArrowRight } from "lucide-react"
import { Link } from "react-router"

import { ChartCard } from "@/components/chart-card"
import { KpiCard } from "@/components/kpi-card"
import { PageBody } from "@/components/page-body"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useApi } from "@/lib/api"
import type { Overview } from "@/lib/types"

export function OverviewPage() {
  const state = useApi<Overview>("/api/overview")

  return (
    <PageBody state={state} needs={["monthly", "analysis", "metrics", "forecasts"]}>
      {(data) => (
        <>
          <section
            aria-label="Key figures"
            className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
          >
            {data.kpis.map((kpi) => (
              <KpiCard key={kpi.key} kpi={kpi} />
            ))}
          </section>

          <ChartCard chart={data.chart} height={360} />

          <section aria-label="Findings" className="grid gap-4 md:grid-cols-2">
            {data.highlights.map((item) => (
              <Card key={item.title}>
                <CardHeader>
                  <CardDescription>{item.title}</CardDescription>
                  <CardTitle className="text-base leading-snug font-medium">{item.text}</CardTitle>
                </CardHeader>
                <CardContent>
                  <Link
                    to={item.href}
                    className="inline-flex items-center gap-1 text-sm font-medium underline-offset-4 hover:underline"
                  >
                    See the details
                    <ArrowRight className="size-4" aria-hidden />
                  </Link>
                </CardContent>
              </Card>
            ))}
          </section>
        </>
      )}
    </PageBody>
  )
}
