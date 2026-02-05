import { Checkbox } from "@/components/ui/checkbox"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function FeaturesPanel({
  features,
  onToggle,
}: {
  features: Record<string, boolean>
  onToggle: (name: string, enabled: boolean) => Promise<void>
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Features</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {Object.entries(features).map(([name, enabled]) => (
          <label key={name} className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={enabled}
              onCheckedChange={(checked) => onToggle(name, checked === true)}
            />
            {name}
          </label>
        ))}
      </CardContent>
    </Card>
  )
}
