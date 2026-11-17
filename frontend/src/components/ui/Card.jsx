/** Base surface for grouped content — the single visual container used across the app. */
import { spotlightHandlers } from '../../motion/interactions.js'

export default function Card({ children, className = '', as: Tag = 'div', interactive = false, ...rest }) {
  const hover = interactive ? spotlightHandlers() : {}
  return (
    <Tag
      className={`rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] ${interactive ? 'spotlight' : ''} ${className}`}
      data-reveal
      {...hover}
      {...rest}
    >
      {children}
    </Tag>
  )
}
