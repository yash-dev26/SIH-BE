import type { ButtonHTMLAttributes } from "react";

export function Button({
  className = "",
  variant = "gold",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "gold" | "ghost" }) {
  const styles =
    variant === "gold"
      ? "bg-gold text-ink shadow-[0_4px_12px_rgba(232,163,61,0.22)] hover:brightness-95"
      : "border border-line bg-paper text-ink hover:bg-ice";
  return (
    <button
      className={`inline-flex h-11 items-center justify-center px-5 text-[13px] font-semibold tracking-wide disabled:opacity-50 ${styles} ${className}`}
      {...props}
    />
  );
}
