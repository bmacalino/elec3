import type { ReactNode } from "react"
import { CircleCheck, CircleDashed, TriangleAlert } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { usePipelineStatus } from "@/hooks/use-pipeline-status"
import type { OutputKey } from "@/lib/api"

function StatusBadge({ done, label }: { done: boolean; label: string }) {
  return (
    <Badge variant={done ? "secondary" : "outline"}>
      {done ? <CircleCheck /> : <CircleDashed />}
      {label}
    </Badge>
  )
}

function Row({
  name,
  detail,
  done,
  label,
}: {
  name: string
  detail: string
  done: boolean
  label: string
}) {
  return (
    <li className="flex items-center justify-between gap-4 py-2">
      <div className="min-w-0">
        <p className="text-sm">{name}</p>
        <p className="truncate font-mono text-xs text-muted-foreground">
          {detail}
        </p>
      </div>
      <StatusBadge done={done} label={label} />
    </li>
  )
}

/** Shown in place of a page's content until the files it reads exist. */
export function PipelineStatus({ needs }: { needs: OutputKey[] }) {
  const state = usePipelineStatus()

  if (state.phase === "loading") {
    return <Skeleton className="h-64 w-full max-w-2xl" />
  }

  if (state.phase === "error") {
    return (
      <Alert variant="destructive" className="max-w-2xl">
        <TriangleAlert />
        <AlertTitle>Cannot reach the API</AlertTitle>
        <AlertDescription>
          Start it from the project folder with{" "}
          <code className="font-mono">.venv\Scripts\python run.py</code>, then
          reload this page.
        </AlertDescription>
      </Alert>
    )
  }

  const { raw, outputs } = state.status
  const needed = outputs.filter((output) => needs.includes(output.key))
  const rawMissing = raw.some((file) => file.found === null)
  const outputsMissing = needed.some((output) => !output.exists)

  let nextStep: ReactNode
  if (rawMissing) {
    nextStep = (
      <>
        Add the missing files to <code className="font-mono">data/raw</code>,
        then reload this page.
      </>
    )
  } else if (outputsMissing) {
    nextStep = (
      <>
        Every raw file is in place. Run{" "}
        <code className="font-mono">
          .venv\Scripts\python -m remittrend.pipeline all
        </code>{" "}
        to produce the files this page reads.
      </>
    )
  } else {
    nextStep = <>The data is ready. This page has not been built yet.</>
  }

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>No data to show yet</CardTitle>
        <CardDescription>{nextStep}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <section>
          <h3 className="text-xs font-medium text-muted-foreground">
            Raw files
          </h3>
          <ul className="divide-y">
            {raw.map((file) => (
              <Row
                key={file.key}
                name={`${file.label} (${file.source})`}
                detail={`data/raw/${file.found ?? file.expected}`}
                done={file.found !== null}
                label={file.found !== null ? "Found" : "Missing"}
              />
            ))}
          </ul>
        </section>
        <section>
          <h3 className="text-xs font-medium text-muted-foreground">
            Files this page reads
          </h3>
          <ul className="divide-y">
            {needed.map((output) => (
              <Row
                key={output.key}
                name={output.path.split("/").pop() ?? output.path}
                detail={output.path}
                done={output.exists}
                label={output.exists ? "Ready" : "Not created"}
              />
            ))}
          </ul>
        </section>
      </CardContent>
    </Card>
  )
}
