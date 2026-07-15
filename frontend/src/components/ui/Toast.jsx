import { useState, useCallback } from 'react'

const TOAST_STYLES = {
  success: 'bg-[var(--color-positive-soft)] text-[var(--color-positive)]',
  error: 'bg-[var(--color-negative-soft)] text-[var(--color-negative)]',
}

export default function Toast({ toasts, removeToast }) {
  if (!toasts.length) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`flex items-center gap-3 rounded-lg px-4 py-3 shadow-lg ${TOAST_STYLES[toast.type] || TOAST_STYLES.success}`}
        >
          <span className="text-sm font-medium">{toast.message}</span>
          <button onClick={() => removeToast(toast.id)} className="text-xs opacity-70 hover:opacity-100">
            Dismiss
          </button>
        </div>
      ))}
    </div>
  )
}

export function useToast() {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, type = 'success') => {
    const id = Date.now()
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 4000)
  }, [])

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return { toasts, addToast, removeToast }
}
