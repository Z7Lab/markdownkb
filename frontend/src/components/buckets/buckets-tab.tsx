import { useEffect, useState } from "react"
import { useBuckets } from "@/hooks/use-buckets"
import { setVisibilityInterval } from "@/lib/polling"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
import { BucketsSidebar } from "./buckets-sidebar"
import { BucketCreateForm } from "./bucket-create-form"
import { BucketDetailPanel } from "./bucket-detail-panel"
import { BucketsEmptyState } from "./buckets-empty-state"

export function BucketsTab() {
  const { buckets, createBucket, updateBucket, deleteBucket, exportBucket, importBucket, promoteBucket, refresh } = useBuckets()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [viewing, setViewing] = useState<{ path: string; bucketId: string } | null>(null)

  // Poll for updates — faster when any bucket is indexing (pauses when tab hidden)
  const anyIndexing = buckets.some((b) => b.indexing)
  useEffect(() => {
    return setVisibilityInterval(refresh, anyIndexing ? 3000 : 15000)
  }, [refresh, anyIndexing])

  // If selected bucket was deleted, deselect it
  useEffect(() => {
    if (selectedId && !buckets.find((b) => b.id === selectedId)) {
      setSelectedId(null)
    }
  }, [buckets, selectedId])

  const selectedBucket = buckets.find((b) => b.id === selectedId) ?? null

  function handleSelectBucket(id: string) {
    setCreating(false)
    setSelectedId(id)
  }

  function handleNewBucket() {
    setSelectedId(null)
    setCreating(true)
  }

  async function handleDelete() {
    if (!confirmDelete) return
    await deleteBucket(confirmDelete)
    setConfirmDelete(null)
  }

  return (
    <div className="flex h-full overflow-hidden">
      <BucketsSidebar
        buckets={buckets}
        selectedId={creating ? null : selectedId}
        onSelect={handleSelectBucket}
        onNewBucket={handleNewBucket}
        onImport={async (file) => {
          const bucket = await importBucket(file)
          if (bucket) {
            setCreating(false)
            setSelectedId(bucket.id)
          }
        }}
      />

      <div className="flex-1 min-w-0 overflow-hidden">
        {creating && (
          <BucketCreateForm
            createBucket={createBucket}
            onCreated={(id) => {
              setCreating(false)
              setSelectedId(id)
            }}
            onCancel={() => setCreating(false)}
          />
        )}

        {!creating && selectedBucket && (
          <BucketDetailPanel
            bucket={selectedBucket}
            onDelete={setConfirmDelete}
            onViewFile={(path) => setViewing({ path, bucketId: selectedBucket.id })}
            updateBucket={updateBucket}
            exportBucket={exportBucket}
            promoteBucket={promoteBucket}
            refresh={refresh}
          />
        )}

        {!creating && !selectedBucket && (
          <BucketsEmptyState onNewBucket={handleNewBucket} />
        )}
      </div>

      <FileViewerDialog
        path={viewing?.path ?? null}
        bucketId={viewing?.bucketId}
        onClose={() => setViewing(null)}
      />

      <ConfirmDialog
        open={confirmDelete !== null}
        onOpenChange={(open) => { if (!open) setConfirmDelete(null) }}
        title="Delete bucket?"
        description={`This will permanently delete the bucket "${buckets.find((b) => b.id === confirmDelete)?.name}" and all its indexed content.`}
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={handleDelete}
      />
    </div>
  )
}
