export function OfflinePage() {
  return (
    <main className="offline-page">
      <div className="offline-glow offline-glow-one" />
      <div className="offline-glow offline-glow-two" />

      <section className="offline-card" aria-labelledby="offline-title">
        <div className="offline-mark" aria-hidden="true">
          <svg viewBox="0 0 72 72" fill="none">
            <path d="M18 53V21.5C18 19.57 19.57 18 21.5 18H44l10 10v25a3 3 0 0 1-3 3H21a3 3 0 0 1-3-3Z" />
            <path d="M44 18v10h10M27 36h18M27 44h12" />
            <circle cx="53" cy="53" r="10" />
            <path d="m49.5 53 2.3 2.3 4.7-5" />
          </svg>
        </div>

        <div className="offline-status">
          <span />
          In the works
        </div>

        <h1 id="offline-title">Something thoughtful is taking shape.</h1>
        <p>
          Literae is currently under development. We&apos;re refining the experience
          before opening the doors.
        </p>

        <div className="offline-rule" aria-hidden="true">
          <span />
        </div>
        <p className="offline-note">Please check back soon.</p>
      </section>
    </main>
  );
}
