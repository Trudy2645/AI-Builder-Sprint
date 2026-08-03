interface LogoProps {
  compact?: boolean;
  className?: string;
}

export function Logo({ compact = false, className = "" }: LogoProps) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <svg
        width="28"
        height="28"
        viewBox="0 0 28 28"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        className="shrink-0"
      >
        <rect width="28" height="28" rx="8" fill="var(--navy)" />
        <path
          d="M4 18c2.2 0 2.2-2.2 4.4-2.2S10.6 18 12.8 18s2.2-2.2 4.4-2.2S19.4 18 21.6 18 23.8 15.8 26 15.8"
          stroke="var(--teal)"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <path
          d="M4 22c2.2 0 2.2-2.2 4.4-2.2S10.6 22 12.8 22s2.2-2.2 4.4-2.2S19.4 22 21.6 22 23.8 19.8 26 19.8"
          stroke="var(--ocean)"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <circle cx="14" cy="9" r="3" fill="var(--ocean)" />
      </svg>
      {!compact && (
        <span className="whitespace-nowrap" style={{ fontWeight: 700, color: "var(--navy)" }}>
          찍어보소
        </span>
      )}
    </div>
  );
}
