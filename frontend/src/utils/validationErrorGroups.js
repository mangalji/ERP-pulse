function stableValue(value) {
  if (value === undefined) return 'undefined'
  try {
    if (Array.isArray(value)) {
      return `[${value.map(stableValue).join(',')}]`
    }
    if (value && typeof value === 'object') {
      return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableValue(value[key])}`).join(',')}}`
    }
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function lineForIndex(lineItems, lineIndex) {
  const index = Number(lineIndex)
  if (!Number.isInteger(index) || index < 1 || index > lineItems.length) return null
  const line = lineItems[index - 1]
  return line && typeof line === 'object' ? line : null
}

function errorWithoutLineReferences(error) {
  return Object.fromEntries(
    Object.entries(error || {}).filter(([key]) => key !== 'line_index' && key !== 'affected_lines'),
  )
}

export function groupValidationErrors(errors, lineItems) {
  const sourceErrors = Array.isArray(errors) ? errors : []
  const sourceLines = Array.isArray(lineItems) ? lineItems : []
  const groups = []
  const byKey = new Map()

  sourceErrors.forEach((rawError, errorIndex) => {
    if (!rawError || typeof rawError !== 'object') return

    const rawAffectedLines = Array.isArray(rawError.affected_lines)
      ? rawError.affected_lines
      : rawError.line_index !== undefined && rawError.line_index !== null
        ? [rawError.line_index]
        : []
    const affectedLines = [...new Set(rawAffectedLines
      .map(Number)
      .filter((lineIndex) => Number.isInteger(lineIndex) && lineIndex > 0))]
    const lineValues = affectedLines.map((lineIndex) => stableValue(lineForIndex(sourceLines, lineIndex))).sort()
    const key = stableValue({
      scope: affectedLines.length ? 'line' : 'header',
      error: errorWithoutLineReferences(rawError),
      line_values: affectedLines.length ? lineValues : [],
    })
    const existing = byKey.get(key)

    if (existing) {
      existing.errorIndexes.push(errorIndex)
      affectedLines.forEach((lineIndex) => {
        if (!existing.affectedLines.includes(lineIndex)) existing.affectedLines.push(lineIndex)
      })
      return
    }

    const group = {
      error: rawError,
      representativeErrorIndex: errorIndex,
      errorIndexes: [errorIndex],
      affectedLines,
    }
    byKey.set(key, group)
    groups.push(group)
  })

  return groups.map((group) => ({
    ...group,
    affectedLines: [...group.affectedLines].sort((a, b) => a - b),
    affectedCount: group.affectedLines.length,
  }))
}

export function formatAffectedLines(lines) {
  const values = [...new Set((Array.isArray(lines) ? lines : [])
    .map(Number)
    .filter((line) => Number.isInteger(line) && line > 0))]
    .sort((a, b) => a - b)
  if (!values.length) return ''

  const ranges = []
  let start = values[0]
  let end = values[0]
  values.slice(1).forEach((value) => {
    if (value === end + 1) {
      end = value
      return
    }
    ranges.push(start === end ? String(start) : `${start}–${end}`)
    start = value
    end = value
  })
  ranges.push(start === end ? String(start) : `${start}–${end}`)
  return ranges.join(', ')
}
