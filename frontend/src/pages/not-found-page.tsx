import { Link } from "react-router"

import { Button } from "@/components/ui/button"

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-start gap-4">
      <p className="text-sm text-muted-foreground">
        There is no page at this address.
      </p>
      <Button asChild variant="outline">
        <Link to="/">Go to Overview</Link>
      </Button>
    </div>
  )
}
