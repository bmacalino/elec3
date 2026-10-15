import { Outlet, useLocation } from "react-router"

import { AppSidebar } from "@/components/app-sidebar"
import { ThemeToggle } from "@/components/theme"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { navItems } from "@/lib/nav"

export function AppLayout() {
  const { pathname } = useLocation()
  const current = navItems.find((item) => item.path === pathname)

  return (
    <SidebarProvider>
      <AppSidebar />
      {/* min-w-0 lets the page be narrower than its widest table, which then scrolls in its card. */}
      <SidebarInset className="min-w-0">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator
            orientation="vertical"
            className="mr-2 data-vertical:h-4 data-vertical:self-center"
          />
          <h1 className="text-sm font-medium">
            {current?.title ?? "Page not found"}
          </h1>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </header>
        <main className="min-w-0 flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
