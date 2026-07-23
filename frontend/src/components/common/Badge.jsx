/* Hallmark · component: badge · genre: modern-minimal · theme: design.md
 * states: default · success · warning · critical · primary · info
 * contrast: pass
 */
export default function Badge({ children, variant = "default" }) {
  const styles = {
    default: "bg-paper-2 text-ink-2",
    success: "bg-success/10 text-success",
    warning: "bg-warning/10 text-warning",
    critical: "bg-critical/10 text-critical",
    primary: "bg-accent/10 text-accent",
    info: "bg-paper-2 text-ink-2",
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${
        styles[variant] || styles.default
      }`}
    >
      {children}
    </span>
  );
}
