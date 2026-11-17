import { useEffect, useState } from 'react'

const COOLDOWN_PATTERN = /Please wait (\d+) more second\(s\) before requesting new code\./i

export default function CooldownMessage({ message }) {
  const match = message?.match(COOLDOWN_PATTERN)
  const initialSeconds = match ? Number(match[1]) : null
  const [secondsRemaining, setSecondsRemaining] = useState(initialSeconds)

  useEffect(() => {
    setSecondsRemaining(initialSeconds)
  }, [initialSeconds, message])

  useEffect(() => {
    if (secondsRemaining === null || secondsRemaining <= 0) return undefined

    const timer = setInterval(() => {
      setSecondsRemaining((seconds) => Math.max(seconds - 1, 0))
    }, 1000)

    return () => clearInterval(timer)
  }, [secondsRemaining])

  if (initialSeconds === null) return message
  if (secondsRemaining <= 0) return 'You can request a new code now.'

  return `Please wait ${secondsRemaining} more second(s) before requesting new code.`
}
