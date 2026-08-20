const PORTFOLIO_URL = 'https://mangalji.github.io/Portfolio/'

/** Persistent footer shown on every page. Links out to the developer's portfolio. */
export default function Footer() {
  return (
    <footer className="mt-auto border-t border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-4 sm:px-6 lg:px-8">
      <div className="flex flex-col items-center justify-center gap-1 text-center text-xs text-[var(--color-muted)] sm:flex-row sm:gap-1.5">
        <span>&copy; {new Date().getFullYear()} AGSuite ERP.</span>
        <a
          href={PORTFOLIO_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-[var(--color-primary)] transition-colors hover:text-[var(--color-primary-dark)]"
        >
          Developed by Raj Mangal
        </a>
      </div>
    </footer>
  )
}
