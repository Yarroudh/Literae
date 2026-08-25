export function OfflinePage() {
  return (
    <main className="offline-page">
      <div className="offline-noise" aria-hidden="true" />

      <header className="offline-header">
        <div className="offline-brand">
          <span className="offline-brand-mark" aria-hidden="true">L</span>
          <span>Literae</span>
        </div>
        <div className="offline-status"><span />Building quietly</div>
      </header>

      <section className="offline-hero" aria-labelledby="offline-title">
        <div className="offline-copy">
          <p className="offline-eyebrow">Research, reimagined</p>
          <h1 id="offline-title">A clearer way to explore knowledge.</h1>
          <p className="offline-description">
            Literae is taking shape behind the scenes. We&apos;re crafting a more
            thoughtful way to discover, connect, and understand research.
          </p>
          <div className="offline-signoff">
            <span aria-hidden="true" />
            Opening soon
          </div>
        </div>

        <div className="offline-visual" aria-hidden="true">
          <svg viewBox="0 0 520 520" fill="none">
            <circle className="offline-orbit orbit-one" cx="260" cy="260" r="181" />
            <circle className="offline-orbit orbit-two" cx="260" cy="260" r="126" />
            <path className="offline-thread" d="M102 306C153 275 160 195 226 191c73-5 75 111 149 93 25-6 39-23 49-47" />
            <path className="offline-thread thread-two" d="M138 137c54 31 60 100 119 119 54 17 87-18 125-55" />
            <circle className="offline-node node-a" cx="102" cy="306" r="8" />
            <circle className="offline-node node-b" cx="138" cy="137" r="6" />
            <circle className="offline-node node-c" cx="424" cy="237" r="7" />
            <circle className="offline-node node-d" cx="382" cy="201" r="5" />
            <g className="offline-paper">
              <rect x="202" y="158" width="132" height="176" rx="18" />
              <path d="M229 205h78M229 229h60M229 253h70M229 291h36" />
              <circle cx="295" cy="291" r="12" />
              <path d="m290 291 3.5 3.5 7-8" />
            </g>
          </svg>
          <span className="offline-pill pill-one">Discover</span>
          <span className="offline-pill pill-two">Connect</span>
          <span className="offline-pill pill-three">Understand</span>
        </div>
      </section>

      <footer className="offline-footer">
        <span>© {new Date().getFullYear()} Literae</span>
        <span>Built for curious minds</span>
      </footer>
    </main>
  );
}
