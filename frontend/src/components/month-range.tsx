import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { monthLabel, monthsBack, monthsBetween } from "@/lib/format"

type Selection = { start: string; end: string }

const PRESETS = [
  { label: "All", months: null },
  { label: "Last 5 years", months: 60 },
  { label: "Last 3 years", months: 36 },
  { label: "Last 12 months", months: 12 },
]

/** Start and end month for everything on the page, with common ranges one click away. */
export function MonthRangeFilter({
  min,
  max,
  value,
  onChange,
}: {
  min: string
  max: string
  value: Selection
  onChange: (selection: Selection) => void
}) {
  const months = monthsBetween(min, max)

  return (
    <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
      <div className="flex flex-wrap gap-2" role="group" aria-label="Quick ranges">
        {PRESETS.map((preset) => {
          const start = preset.months === null ? min : monthsBack(max, preset.months, min)
          const active = value.start === start && value.end === max
          return (
            <Button
              key={preset.label}
              size="sm"
              variant={active ? "default" : "outline"}
              aria-pressed={active}
              onClick={() => onChange({ start, end: max })}
            >
              {preset.label}
            </Button>
          )
        })}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="range-start">From</Label>
          <Select
            value={value.start}
            onValueChange={(start) =>
              onChange({ start, end: start > value.end ? start : value.end })
            }
          >
            <SelectTrigger id="range-start" className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {months.map((month) => (
                <SelectItem key={month} value={month}>
                  {monthLabel(month)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="range-end">To</Label>
          <Select
            value={value.end}
            onValueChange={(end) =>
              onChange({ start: end < value.start ? end : value.start, end })
            }
          >
            <SelectTrigger id="range-end" className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {months.map((month) => (
                <SelectItem key={month} value={month}>
                  {monthLabel(month)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  )
}
