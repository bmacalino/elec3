import * as React from "react"

export type OutputKey =
  | "monthly"
  | "by_source"
  | "by_country"
  | "analysis"
  | "metrics"
  | "forecasts"

export type RawFileStatus = {
  key: string
  label: string
  source: string
  expected: string
  found: string | null
}

export type OutputStatus = {
  key: OutputKey
  path: string
  exists: boolean
}

export type PipelineStatus = {
  raw: RawFileStatus[]
  outputs: OutputStatus[]
}

export type ApiError = {
  /** not_ready: the pipeline has not produced the files; network: Flask is not running. */
  kind: "not_ready" | "bad_request" | "network" | "server"
  message: string
}

export type ApiState<T> = {
  data: T | null
  loading: boolean
  error: ApiError | null
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, { signal })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw { kind: "network", message: "Cannot reach the API." } satisfies ApiError
  }
  if (response.ok) return (await response.json()) as T

  let body: { error?: string; message?: string } = {}
  try {
    body = await response.json()
  } catch {
    // Not JSON: the proxy answers this way when Flask is not running.
  }
  if (body.error === "not_ready" || body.error === "bad_request") {
    throw { kind: body.error, message: body.message ?? "" } satisfies ApiError
  }
  throw {
    kind: response.status >= 502 ? "network" : "server",
    message: body.message ?? `The server answered ${response.status}.`,
  } satisfies ApiError
}

export function getStatus(signal?: AbortSignal): Promise<PipelineStatus> {
  return getJson<PipelineStatus>("/api/status", signal)
}

/**
 * Loads a page's data, and again whenever the path (with its query) changes.
 * While a new request is running the previous data stays, so the page does
 * not flash empty when a filter changes.
 */
export function useApi<T>(path: string): ApiState<T> {
  // `answered` is the path the stored result belongs to; until it matches the
  // requested path, a request is still running.
  const [result, setResult] = React.useState<{
    answered: string | null
    data: T | null
    error: ApiError | null
  }>({ answered: null, data: null, error: null })

  React.useEffect(() => {
    const controller = new AbortController()
    getJson<T>(path, controller.signal)
      .then((data) => setResult({ answered: path, data, error: null }))
      .catch((error: ApiError) => {
        if (controller.signal.aborted) return
        setResult((previous) => ({
          answered: path,
          // A rejected filter keeps the page as it was; anything else clears it.
          data: error.kind === "bad_request" ? previous.data : null,
          error,
        }))
      })
    return () => controller.abort()
  }, [path])

  return { data: result.data, error: result.error, loading: result.answered !== path }
}

/** "/api/history" + { start: "2024-01", end: undefined } -> "/api/history?start=2024-01" */
export function withQuery(
  path: string,
  query: Record<string, string | number | null | undefined>,
): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== null && value !== undefined && value !== "") params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `${path}?${text}` : path
}
