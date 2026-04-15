import * as React from "react"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Continue",
  cancelLabel = "Cancel",
  variant = "destructive",
  onConfirm,
  onCancel,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: React.ReactNode
  confirmLabel?: string
  cancelLabel?: string
  variant?: "default" | "destructive"
  onConfirm: () => void
  onCancel?: () => void
}) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onCancel}>{cancelLabel}</AlertDialogCancel>
          <AlertDialogAction variant={variant} onClick={onConfirm}>
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
