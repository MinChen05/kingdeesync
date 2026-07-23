/* Hallmark · component: button · genre: modern-minimal · theme: design.md
 * states: default · hover · focus · active · disabled · loading · error · success
 * contrast: pass
 */
export default function Button({
  children,
  variant = "primary",
  size = "md",
  onClick,
  disabled,
  type = "button",
  className = "",
  loading = false,
}) {
  const base =
    "inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-all duration-120 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-40 active:translate-y-px";

  const variants = {
    primary: "bg-accent text-white hover:bg-accent-2",
    secondary: "border border-rule text-ink hover:bg-paper-2",
    ghost: "text-ink-2 hover:text-ink hover:bg-paper-2",
    danger: "bg-critical text-white hover:bg-critical/90",
    success: "bg-success text-white hover:bg-success/90",
  };

  const sizes = {
    xs: "px-2.5 py-1 text-xs",
    sm: "px-3 py-1.5 text-xs",
    md: "px-4 py-2 text-sm",
    lg: "px-5 py-2.5 text-sm",
  };

  return (
    <button
      type={type}
      className={`${base} ${variants[variant] || variants.primary} ${sizes[size] || sizes.md} ${className}`}
      onClick={onClick}
      disabled={disabled || loading}
    >
      {loading && (
        <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
      )}
      {!loading && children}
    </button>
  );
}
