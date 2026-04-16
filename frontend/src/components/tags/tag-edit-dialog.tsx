import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { X, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { useSettings } from "@/hooks/use-settings";

interface TagEditDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentTags: string[];
  filePath: string;
  isIndexed: boolean;
  onSave: (
    tags: string[],
    createBackup: boolean,
    shouldReindex: boolean,
  ) => Promise<void>;
}

export function TagEditDialog({
  open,
  onOpenChange,
  currentTags,
  filePath,
  isIndexed,
  onSave,
}: TagEditDialogProps) {
  const [tags, setTags] = useState<string[]>(currentTags);
  const [inputValue, setInputValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [createBackup, setCreateBackup] = useState(true);
  const [shouldReindex, setShouldReindex] = useState(false);
  const { settings } = useSettings();

  const [tagGenEnabled, setTagGenEnabled] = useState(false);

  // Fetch tags plugin config to check AI generation enabled
  useEffect(() => {
    api.get<{ plugin: string; config: Record<string, unknown> }>("/api/v1/settings/plugins/tags")
      .then((res) => setTagGenEnabled(res.config.ai_generation === true))
      .catch(() => setTagGenEnabled(false));
  }, [settings]);

  // Set default backup checkbox from settings
  useEffect(() => {
    if (settings?.mcp?.tag_generator) {
      const config = settings.mcp.tag_generator as { create_backup?: boolean };
      setCreateBackup(config.create_backup !== false);
    }
  }, [settings]);

  // Reset tags when dialog opens with new currentTags
  useEffect(() => {
    if (open) {
      setTags(currentTags);
    }
  }, [open, currentTags]);

  const handleAddTag = () => {
    const newTag = inputValue.trim().toLowerCase().replace(/\s+/g, "-");
    if (newTag && !tags.includes(newTag)) {
      setTags([...tags, newTag]);
      setInputValue("");
    }
  };

  const handleRemoveTag = (tagToRemove: string) => {
    setTags(tags.filter((t) => t !== tagToRemove));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddTag();
    }
  };

  const handleGenerateTags = async () => {
    setGenerating(true);

    try {
      const res = await api.post<{
        status: string;
        suggested_tags: string[];
        preview: string;
        message: string;
      }>("/api/v1/tags/generate", {
        file_path: filePath,
        use_similar_docs: true,
        auto_apply: false,
      });

      if (res.status === "success") {
        toast.success(res.message);
        // Add generated tags to existing ones (avoiding duplicates)
        const newTags = [...tags];
        for (const tag of res.suggested_tags) {
          if (!newTags.includes(tag)) {
            newTags.push(tag);
          }
        }
        setTags(newTags);
      }
    } catch (err) {
      toast.error(`Failed to generate tags: ${(err as Error).message}`);
    } finally {
      setGenerating(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(tags, createBackup, shouldReindex);
      onOpenChange(false);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setTags(currentTags);
    setInputValue("");
    onOpenChange(false);
  };

  function generateBackupFilename(filename: string): string {
    const now = new Date();
    const timestamp = now
      .toISOString()
      .replace(/[-:]/g, "")
      .replace(/\.\d{3}Z$/, "")
      .replace("T", "_")
      .slice(0, 15); // YYYYMMDD_HHMMSS

    const nameParts = filename.split(".");
    const ext = nameParts.pop();
    const baseName = nameParts.join(".");

    return `${baseName}.${timestamp}.backup.${ext}`;
  }

  const filename = filePath.split("/").pop() ?? "";
  const directory = filePath.split("/").slice(0, -1).join("/") ?? "";
  const backupFilename = generateBackupFilename(filename);
  const fullBackupPath = `${directory}/${backupFilename}`;

  return (
    <Dialog open={open} onOpenChange={handleCancel}>
      <DialogContent className="max-w-4xl w-[90vw]">
        <DialogHeader>
          <DialogTitle>Edit Tags</DialogTitle>
          <DialogDescription>
            Manually add/remove tags or use AI to generate suggestions.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* AI Generation Section */}
          {tagGenEnabled && (
            <>
              <div className="space-y-2">
                <span className="text-sm font-medium">AI Generation</span>
                <Button
                  onClick={handleGenerateTags}
                  disabled={generating || saving}
                  variant="outline"
                  className="w-full"
                >
                  <Sparkles className="h-4 w-4 mr-2" />
                  {generating ? "Generating..." : "Generate Tags with AI"}
                </Button>
                <p className="text-xs text-muted-foreground">
                  AI will analyze the document and suggest relevant tags based
                  on content and similar documents.
                </p>
              </div>
              <Separator />
            </>
          )}

          {/* Manual Tag Entry */}
          <div className="space-y-2">
            <label htmlFor="tag-input" className="text-sm font-medium">
              Add tag manually
            </label>
            <div className="flex gap-2">
              <Input
                id="tag-input"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="e.g., web-development"
                className="flex-1"
                disabled={generating || saving}
              />
              <Button
                onClick={handleAddTag}
                variant="outline"
                disabled={generating || saving}
              >
                Add
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Press Enter to add. Tags will be converted to lowercase-hyphenated
              format.
            </p>
          </div>

          {/* Current Tags Display */}
          <div className="space-y-2">
            <label className="text-sm font-medium">
              Current tags ({tags.length})
            </label>
            {tags.length > 0 ? (
              <div className="flex flex-wrap gap-2 p-3 border rounded-md min-h-[60px]">
                {tags.map((tag) => (
                  <Badge key={tag} variant="secondary" className="pr-1">
                    {tag}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-4 w-4 ml-1 hover:bg-transparent"
                      onClick={() => handleRemoveTag(tag)}
                      disabled={generating || saving}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </Badge>
                ))}
              </div>
            ) : (
              <div className="p-3 border rounded-md min-h-[60px] flex items-center justify-center">
                <p className="text-sm text-muted-foreground italic">
                  No tags yet
                </p>
              </div>
            )}
          </div>

          <Separator />

          {/* Save Options */}
          <div className="space-y-3">
            <span className="text-sm font-medium">Save options</span>

            <div className="flex items-start space-x-2 rounded-md border p-3">
              <Checkbox
                id="create-backup"
                checked={createBackup}
                onCheckedChange={(checked) => setCreateBackup(checked === true)}
                disabled={generating || saving}
                className="shrink-0"
              />
              <div className="flex-1 space-y-1">
                <Label
                  htmlFor="create-backup"
                  className="text-sm font-medium leading-none cursor-pointer"
                >
                  Create backup before modifying
                </Label>
                {createBackup && (
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <p className="text-xs text-muted-foreground font-mono break-all whitespace-pre-wrap">
                          {fullBackupPath}
                        </p>
                      </TooltipTrigger>
                      <TooltipContent side="bottom" className="max-w-md">
                        <p className="font-mono text-xs break-all">
                          {fullBackupPath}
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                )}
              </div>
            </div>

            <div className="flex items-start space-x-2 rounded-md border p-3">
              <Checkbox
                id="should-reindex"
                checked={shouldReindex}
                onCheckedChange={(checked) =>
                  setShouldReindex(checked === true)
                }
                disabled={generating || saving}
              />
              <div className="flex-1 space-y-1">
                <Label
                  htmlFor="should-reindex"
                  className="text-sm font-medium leading-none cursor-pointer"
                >
                  {isIndexed
                    ? "Reindex file after saving"
                    : "Index file after saving"}
                </Label>
                <p className="text-xs text-muted-foreground">
                  {isIndexed
                    ? "Update search index with new tags"
                    : "Add this file to the search index"}
                </p>
              </div>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={handleCancel}
            disabled={generating || saving}
          >
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={generating || saving}>
            {saving ? "Saving..." : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
