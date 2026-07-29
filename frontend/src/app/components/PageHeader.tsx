import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-col gap-3 sm:mb-6 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
      <div className="min-w-0">
        <h1 className="break-words text-xl sm:text-2xl" style={{ color: "var(--navy)" }}>
          {title}
        </h1>
        {description && (
          <p className="mt-1 break-words text-muted-foreground" style={{ fontSize: "14px" }}>
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:shrink-0">{actions}</div>}
    </div>
  );
}
