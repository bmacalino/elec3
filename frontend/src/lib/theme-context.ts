import * as React from "react"

export type Theme = "light" | "dark"

export const ThemeContext = React.createContext<{ theme: Theme; toggle: () => void }>({
  theme: "light",
  toggle: () => {},
})

/** The current theme. Charts read it so they redraw in the new colours. */
export function useTheme() {
  return React.useContext(ThemeContext)
}
