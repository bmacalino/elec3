import type { ComponentProps, ReactNode } from "react"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { TableCell, TableHead } from "@/components/ui/table"
import { cn } from "@/lib/utils"

/** A right-aligned number cell; digits line up down the column. */
export function Num({ className, ...props }: ComponentProps<typeof TableCell>) {
  return <TableCell className={cn("text-right tabular-nums", className)} {...props} />
}

export function NumHead({ className, ...props }: ComponentProps<typeof TableHead>) {
  return <TableHead className={cn("text-right", className)} {...props} />
}

/** A table inside a card. With `scroll`, long tables scroll under a fixed header. */
export function TableCard({
  title,
  description,
  action,
  scroll = false,
  children,
}: {
  title: string
  description?: ReactNode
  action?: ReactNode
  scroll?: boolean
  children: ReactNode
}) {
  return (
    <Card className="min-w-0">
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <CardTitle>{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </div>
        {action}
      </CardHeader>
      <CardContent>
        <div
          className={cn(
            "overflow-x-auto",
            scroll && "max-h-[28rem] overflow-y-auto [&_thead]:sticky [&_thead]:top-0 [&_thead]:bg-card",
          )}
        >
          {children}
        </div>
      </CardContent>
    </Card>
  )
}
