import { useCallback, useEffect, useRef, useState } from 'react'

const DEFAULT_HEIGHT = 600
const MIN_HEIGHT = 420
const VIEWPORT_GUTTER = 180

function clampHeight(height) {
  const maximum = Math.max(MIN_HEIGHT, window.innerHeight - VIEWPORT_GUTTER)
  return Math.min(Math.max(height, MIN_HEIGHT), maximum)
}

export function useWorkspaceHeight() {
  const [workspaceHeight, setWorkspaceHeight] = useState(DEFAULT_HEIGHT)
  const cleanupResizeRef = useRef(null)

  const stopResizing = useCallback(() => {
    cleanupResizeRef.current?.()
    cleanupResizeRef.current = null
  }, [])

  useEffect(() => stopResizing, [stopResizing])

  const startResizing = useCallback((event) => {
    if (event.pointerType === 'mouse' && event.button !== 0) return

    event.preventDefault()
    stopResizing()

    const startY = event.clientY
    const startHeight = workspaceHeight
    const onPointerMove = (moveEvent) => {
      setWorkspaceHeight(clampHeight(startHeight + moveEvent.clientY - startY))
    }
    const onPointerUp = () => stopResizing()

    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp, { once: true })
    cleanupResizeRef.current = () => {
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
    }
  }, [stopResizing, workspaceHeight])

  const resizeWithKeyboard = useCallback((event) => {
    if (!['ArrowDown', 'ArrowUp', 'Home'].includes(event.key)) return

    event.preventDefault()
    setWorkspaceHeight((current) => {
      if (event.key === 'Home') return DEFAULT_HEIGHT
      return clampHeight(current + (event.key === 'ArrowDown' ? 32 : -32))
    })
  }, [])

  return { workspaceHeight, startResizing, resizeWithKeyboard }
}
