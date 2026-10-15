const MINUS = "−"

/** The value as it will be shown; a tiny negative that rounds to zero becomes 0, not -0. */
function rounded(value: number, digits: number): number {
  const result = Number(value.toFixed(digits))
  return result === 0 ? 0 : result
}

export function decimal(value: number, digits = 1): string {
  return rounded(value, digits)
    .toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })
    .replace("-", MINUS)
}

function sign(value: number, digits = 1): string {
  return rounded(value, digits) > 0 ? "+" : ""
}

/** Amounts are stored in US$ million; large ones read better in billions. */
export function usd(million: number): string {
  if (Math.abs(million) >= 1000) return `US$${decimal(million / 1000, 2)} billion`
  return `US$${decimal(million, 1)} million`
}

export function signedUsd(million: number): string {
  return `${million < 0 ? MINUS : "+"}${usd(Math.abs(million))}`
}

export function percent(value: number, digits = 1): string {
  return `${decimal(value, digits)}%`
}

export function signedPercent(value: number, digits = 1): string {
  return `${sign(value, digits)}${decimal(value, digits)}%`
}

export function signedDecimal(value: number, digits = 1): string {
  return `${sign(value, digits)}${decimal(value, digits)}`
}

export function signedPoints(value: number): string {
  const unit = Math.abs(value) === 1 ? "point" : "points"
  return `${signedDecimal(value)} ${unit}`
}

export function peso(value: number): string {
  return `₱${decimal(value, 2)}`
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

/** "2026-06" -> "Jun 2026" */
export function monthLabel(month: string): string {
  const [year, number] = month.split("-")
  return `${MONTHS[Number(number) - 1]} ${year}`
}

/** Every month from start to end inclusive, as "YYYY-MM". */
export function monthsBetween(start: string, end: string): string[] {
  const [startYear, startMonth] = start.split("-").map(Number)
  const [endYear, endMonth] = end.split("-").map(Number)
  const months: string[] = []
  for (let index = startYear * 12 + startMonth - 1; index <= endYear * 12 + endMonth - 1; index++) {
    months.push(`${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`)
  }
  return months
}

/** The month `count - 1` months before `month`, not earlier than `earliest`. */
export function monthsBack(month: string, count: number, earliest: string): string {
  const [year, number] = month.split("-").map(Number)
  const index = year * 12 + number - 1 - (count - 1)
  const text = `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`
  return text < earliest ? earliest : text
}
