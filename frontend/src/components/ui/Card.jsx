/** Base surface for grouped content — the single visual container used across the app. */
export default function Card({ children, className = '', as: Tag = 'div', ...rest }) {
  return (
    <Tag
      className={`rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] ${className}`}
      {...rest}
    >
      {children}
    </Tag>
  )
}
