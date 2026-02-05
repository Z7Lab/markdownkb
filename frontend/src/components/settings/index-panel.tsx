import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function IndexPanel({
  status,
  onReindex,
  onCancel,
}: {
  status: string
  onReindex: () => Promise<void>
  onCancel: () => Promise<void>
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Indexing</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-2">
          <Button onClick={onReindex}>Re-index All Sources</Button>
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        </div>
        {status && (
          <pre className="text-sm bg-muted p-3 rounded-md whitespace-pre-wrap">
            {status}
          </pre>
        )}
      </CardContent>
    </Card>
  )
}
