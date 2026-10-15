import type { ReactNode } from "react"
import { TriangleAlert } from "lucide-react"

import { PipelineStatus } from "@/components/pipeline-status"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import type { ApiState, OutputKey } from "@/lib/api"

/**
 * Shows a page's content once its data has loaded, and the right message
 * when it has not: files still to be produced, the API not running, or a
 * filter the server rejected.
 */
export function PageBody<T>({
  state,
  needs,
  children,
}: {
  state: ApiState<T>
  /** Pipeline outputs the page reads, listed when they are missing. */
  needs: OutputKey[]
  children: (data: T) => ReactNode
}) {
  const { data, loading, error } = state

  if (error && (error.kind === "not_ready" || error.kind === "network")) {
    return <PipelineStatus needs={needs} />
  }
  if (error && !data) {
    return (
      <Alert variant="destructive" className="max-w-2xl">
        <TriangleAlert />
        <AlertTitle>This page could not be loaded</AlertTitle>
        <AlertDescription>{error.message}</AlertDescription>
      </Alert>
    )
  }
  if (!data) {
    return (
      <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-80 w-full" />
      </div>
    )
  }
  return (
    <div className="flex min-w-0 flex-col gap-6">
      {error && (
        <Alert variant="destructive" className="max-w-2xl">
          <TriangleAlert />
          <AlertTitle>That selection cannot be shown</AlertTitle>
          <AlertDescription>{error.message}</AlertDescription>
        </Alert>
      )}
      {/* While a new selection loads, the previous one stays, dimmed. Sections may
          not grow wider than the page: a wide table scrolls inside its own card. */}
      <div
        className={`flex min-w-0 flex-col gap-6 transition-opacity *:min-w-0 ${loading ? "opacity-60" : ""}`}
        aria-busy={loading}
      >
        {children(data)}
      </div>
    </div>
  )
}
