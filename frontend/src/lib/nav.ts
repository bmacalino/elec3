import {
  CalendarRange,
  ChartLine,
  Globe,
  LayoutDashboard,
  Scale,
  Table2,
  TrendingUp,
  Waypoints,
  type LucideIcon,
} from "lucide-react"

export type NavItem = {
  title: string
  path: string
  icon: LucideIcon
}

export type NavGroup = {
  label: string
  items: NavItem[]
}

export const navGroups: NavGroup[] = [
  {
    label: "Dashboard",
    items: [{ title: "Overview", path: "/", icon: LayoutDashboard }],
  },
  {
    label: "Analysis",
    items: [
      { title: "Historical data", path: "/history", icon: Table2 },
      { title: "Trends", path: "/trends", icon: TrendingUp },
      { title: "Seasonality", path: "/seasonality", icon: CalendarRange },
      { title: "Relationships", path: "/relationships", icon: Waypoints },
      { title: "Sources and countries", path: "/sources", icon: Globe },
    ],
  },
  {
    label: "Forecasting",
    items: [
      { title: "Forecast", path: "/forecast", icon: ChartLine },
      { title: "Model comparison", path: "/models", icon: Scale },
    ],
  },
]

export const navItems: NavItem[] = navGroups.flatMap((group) => group.items)
