import { forwardRef, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";

export function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
        {label}
      </span>
      {children}
      {error ? <span className="mt-1 block text-xs text-risk-high">{error}</span> : null}
    </label>
  );
}

const control =
  "h-11 w-full border border-line bg-paper px-3 text-sm text-ink shadow-[0_1px_2px_rgba(15,27,36,0.03)] outline-none transition-colors focus:border-teal focus:ring-2 focus:ring-teal/10";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select(props, ref) {
    return <select ref={ref} className={control} {...props} />;
  },
);

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input(props, ref) {
    return <input ref={ref} className={control} {...props} />;
  },
);
