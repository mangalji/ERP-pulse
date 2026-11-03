import { useState, useCallback } from 'react'

const TOAST_STYLES = {
  success: 'bg-[var(--color-positive-soft)] text-[var(--color-positive)]',
  error: 'bg-[var(--color-negative-soft)] text-[var(--color-negative)]',
}

export default function Toast({ toasts, removeToast, position = 'bottom' }) {
  if (!toasts.length) return null

  return (
    <div className={position === 'top'
      ? 'fixed left-0 right-0 top-16 z-[180] flex w-full flex-col gap-2 px-2 sm:px-4'
      : 'fixed bottom-4 right-4 z-50 flex flex-col gap-2'}>
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`flex w-full items-center gap-3 rounded-lg px-4 py-3 shadow-lg ${TOAST_STYLES[toast.type] || TOAST_STYLES.success}`}
        >
          <span className="min-w-0 flex-1 text-sm font-medium">{toast.message}</span>
          <button onClick={() => removeToast(toast.id)} className="ml-auto shrink-0 text-xs opacity-70 hover:opacity-100">
            Dismiss
          </button>
        </div>
      ))}
    </div>
  )
}

// oxlint-disable-next-line react/only-export-components -- this hook belongs with its Toast renderer.
export function useToast({ autoDismiss = true, latestOnly = false, persist } = {}) {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, type = 'success') => {
    const id = Date.now()
    setToasts((prev) => latestOnly ? [{ id, message, type }] : [...prev, { id, message, type }])
    if (persist) {
      void Promise.resolve(persist(message, type)).catch(() => null)
    }
    if (autoDismiss) {
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id))
      }, 4000)
    }
  }, [autoDismiss, latestOnly, persist])

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return { toasts, addToast, removeToast }
}
