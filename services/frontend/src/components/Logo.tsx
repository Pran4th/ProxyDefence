/**
 * Brand mark for ProxyDefence. Plain inline SVG (no image request, no new
 * dependency) so it stays crisp at any size and adopts the real design-system
 * colors (--primary / --primary-glow) rather than the old baked-in neon PNG.
 * `iconOnly` renders just the shield glyph (navbar/favicon-sized contexts);
 * the wordmark is composed separately by callers that already render their
 * own "ProxyDefence" text next to it.
 */
const Logo = ({ className = "h-9 w-9", iconOnly = true }: { className?: string; iconOnly?: boolean }) => (
  <svg
    viewBox="0 0 100 100"
    className={className}
    role="img"
    aria-label="ProxyDefence"
  >
    <defs>
      <linearGradient id="pd-logo-shield" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="hsl(var(--primary))" />
        <stop offset="100%" stopColor="hsl(var(--primary-glow))" />
      </linearGradient>
    </defs>

    {/* Shield silhouette */}
    <path
      d="M50 4 L88 17 V46 C88 71 71.5 89 50 96 C28.5 89 12 71 12 46 V17 Z"
      fill="url(#pd-logo-shield)"
    />

    {/* Monogram "P" cut as negative space */}
    <path
      d="M40 30 H54 C61 30 66.5 35 66.5 42 C66.5 49 61 54 54 54 H46 V70 H40 Z M46 36 V48 H54 C57.5 48 60.5 45.3 60.5 42 C60.5 38.7 57.5 36 54 36 Z"
      fill="hsl(var(--primary-foreground))"
      fillRule="evenodd"
    />

    {/* Signal pulse accent, ties to the "Live signal" branding used elsewhere */}
    <circle cx="50" cy="14" r="3" fill="hsl(var(--background))" opacity="0.9" />

    {!iconOnly && (
      <text
        x="50"
        y="112"
        textAnchor="middle"
        fontSize="10"
        fontWeight={600}
        fill="hsl(var(--foreground))"
      >
        ProxyDefence
      </text>
    )}
  </svg>
);

export default Logo;
