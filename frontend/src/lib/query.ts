import * as React from "react"
import { useSearchParams } from "react-router"

/**
 * A page's filters, kept in the address bar so a view survives a reload and
 * can be shared as a link. `update` changes some of them; an empty value
 * removes that filter.
 */
export function useQueryParams<Key extends string>(
  keys: readonly Key[],
): [Record<Key, string | null>, (changes: Partial<Record<Key, string | null>>) => void] {
  const [params, setParams] = useSearchParams()

  const values = Object.fromEntries(keys.map((key) => [key, params.get(key)])) as Record<
    Key,
    string | null
  >

  const update = React.useCallback(
    (changes: Partial<Record<Key, string | null>>) => {
      setParams(
        (previous) => {
          const next = new URLSearchParams(previous)
          for (const [key, value] of Object.entries(changes) as [Key, string | null][]) {
            if (value === null || value === "") next.delete(key)
            else next.set(key, value)
          }
          return next
        },
        { replace: true },
      )
    },
    [setParams],
  )

  return [values, update]
}
