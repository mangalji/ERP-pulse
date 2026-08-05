import Button from '../ui/Button.jsx'

/**
 * Confirmation dialog used for destructive or important actions.
 * Renders a modal overlay with confirm/cancel controls.
 */
export default function ConfirmDialog({
  open,
  title = 'Are you sure?',
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  intent = 'primary',
  loading = false,
  onConfirm,
  onCancel,
}) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onCancel} />
      <div className="relative w-full max-w-md rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
        <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">{title}</h3>
        {message && <p className="mt-2 text-sm text-[var(--color-muted)]">{message}</p>}
        <div className="mt-6 flex justify-end gap-2">
          <Button intent="secondary" onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button intent={intent} onClick={onConfirm} isLoading={loading}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
