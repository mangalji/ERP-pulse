export function WorkspaceResizeHandle({ onPointerDown, onKeyDown }) {
  return (
    <div className="hidden lg:flex lg:items-center lg:justify-center">
      <button
        type="button"
        onPointerDown={onPointerDown}
        onKeyDown={onKeyDown}
        className="group flex h-5 w-full cursor-row-resize touch-none items-center justify-center"
        aria-label="Resize OCR workspace"
        title="Drag to resize preview and extracted data"
      >
        <span className="h-1 w-16 rounded-full bg-[var(--color-border)] transition-colors group-hover:bg-[var(--color-primary)]" />
      </button>
    </div>
  )
}
