import { usePathCheck } from "@/hooks/use-path-check"

export interface BucketPathStatusProps {
  path: string
  context?: "create" | "view"
}

export function BucketPathStatus({ path, context = "create" }: BucketPathStatusProps) {
  const check = usePathCheck(path)
  if (check.status === "idle") return null
  if (check.status === "checking") return <p className="text-xs text-muted-foreground mt-1">Checking...</p>
  if (check.status === "ok") return <p className="text-xs text-green-600 dark:text-green-400 mt-1">Path found</p>
  if (check.status === "not_found") return <p className="text-xs text-destructive mt-1">Path not found</p>
  if (check.status === "needs_restart") {
    const msg = context === "view"
      ? "Path not mounted in Docker — restart Docker to apply mount configuration."
      : "Path not mounted — creating this bucket will add the mount and prompt you to restart Docker."
    return <p className="text-xs text-yellow-600 dark:text-yellow-400 mt-1">{msg}</p>
  }
  if (check.status === "bad_mount") {
    return (
      <p className="text-xs text-destructive mt-1">
        Path configured but not accessible — check the host path exists and restart Docker.
      </p>
    )
  }
  return null
}
