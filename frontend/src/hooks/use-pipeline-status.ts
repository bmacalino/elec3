import * as React from "react"

import { getStatus, type PipelineStatus } from "@/lib/api"

type State =
  | { phase: "loading" }
  | { phase: "error" }
  | { phase: "ready"; status: PipelineStatus }

export function usePipelineStatus(): State {
  const [state, setState] = React.useState<State>({ phase: "loading" })

  React.useEffect(() => {
    const controller = new AbortController()
    getStatus(controller.signal)
      .then((status) => setState({ phase: "ready", status }))
      .catch(() => {
        if (!controller.signal.aborted) setState({ phase: "error" })
      })
    return () => controller.abort()
  }, [])

  return state
}
