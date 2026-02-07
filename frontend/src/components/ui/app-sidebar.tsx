import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { ThemeToggle } from "@/components/theme-toggle"
import { useNavigation } from "@/hooks/use-navigation"
import { Settings } from "lucide-react"

export function AppSidebar({
  width = "w-72",
  header,
  children,
  className,
}: {
  width?: string
  header?: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  const { setActiveTab } = useNavigation()

  return (
    <div className={cn("shrink-0 border-r flex flex-col min-h-0 overflow-hidden bg-muted/30", width, className)}>
      {header && (
        <>
          <div className="p-3 shrink-0">{header}</div>
          <Separator />
        </>
      )}
      <ScrollArea className="flex-1 min-h-0">
        {children}
      </ScrollArea>
      <Separator />
      <div className="p-3 shrink-0 flex items-center justify-between">
        <Button
          variant="ghost"
          size="sm"
          className="gap-1.5 text-muted-foreground hover:text-foreground"
          onClick={() => setActiveTab("settings")}
        >
          <Settings className="h-4 w-4" />
          Settings
        </Button>
        <ThemeToggle />
      </div>
    </div>
  )
}
