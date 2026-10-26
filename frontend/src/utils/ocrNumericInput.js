// Keep numeric validation while preventing accidental browser step changes.
export function preventOcrNumberStep(event) {
  if (event.key === 'ArrowUp' || event.key === 'ArrowDown') event.preventDefault()
}

export function blurOcrNumberOnWheel(event) {
  if (document.activeElement === event.currentTarget) event.currentTarget.blur()
}
