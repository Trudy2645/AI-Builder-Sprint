import * as React from "react";

import { cn } from "./utils";

function Textarea({ className, onInput, ...props }: React.ComponentProps<"textarea">) {
  const ref = React.useRef<HTMLTextAreaElement>(null);

  // field-sizing:content is not supported in every browser, so grow the box to
  // fit its content instead of letting long text scroll inside a fixed height.
  const fit = React.useCallback(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, []);

  React.useLayoutEffect(fit, [fit, props.value]);

  return (
    <textarea
      ref={ref}
      data-slot="textarea"
      className={cn(
        "resize-none overflow-hidden border-input placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive dark:bg-input/30 flex field-sizing-content min-h-16 w-full rounded-md border bg-input-background px-3 py-2 text-base transition-[color,box-shadow] outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
        className,
      )}
      onInput={(event) => {
        fit();
        onInput?.(event);
      }}
      {...props}
    />
  );
}

export { Textarea };
