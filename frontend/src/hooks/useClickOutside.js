import { useEffect } from 'react'

export default function useClickOutside(ref, onOutside, enabled = true) {
  useEffect(() => {
    if (!enabled) return undefined

    const handlePointerDown = (event) => {
      if (ref.current && !ref.current.contains(event.target)) onOutside(event)
    }

    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
  }, [enabled, onOutside, ref])
}
