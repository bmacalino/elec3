import type { ReactNode } from "react"
import { Route, Routes } from "react-router"

import { AppLayout } from "@/components/app-layout"
import { navItems } from "@/lib/nav"
import { ForecastPage } from "@/pages/forecast-page"
import { HistoryPage } from "@/pages/history-page"
import { ModelsPage } from "@/pages/models-page"
import { NotFoundPage } from "@/pages/not-found-page"
import { OverviewPage } from "@/pages/overview-page"
import { RelationshipsPage } from "@/pages/relationships-page"
import { SeasonalityPage } from "@/pages/seasonality-page"
import { SourcesPage } from "@/pages/sources-page"
import { TrendsPage } from "@/pages/trends-page"

const PAGES: Record<string, ReactNode> = {
  "/": <OverviewPage />,
  "/history": <HistoryPage />,
  "/trends": <TrendsPage />,
  "/seasonality": <SeasonalityPage />,
  "/relationships": <RelationshipsPage />,
  "/sources": <SourcesPage />,
  "/forecast": <ForecastPage />,
  "/models": <ModelsPage />,
}

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        {navItems.map((item) => (
          <Route key={item.path} path={item.path} element={PAGES[item.path]} />
        ))}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default App
