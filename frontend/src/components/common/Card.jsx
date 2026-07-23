/* Hallmark · component: card · genre: modern-minimal · theme: design.md
 * states: default · hover · elevated
 * contrast: pass
 */
export default function Card({ children, className = "", hover = false, elevated = false }) {
  const base = "bg-paper border rounded-lg";
  const borderClass = elevated ? "border-rule shadow-sm" : "border-rule/60";
  const hoverClass = hover ? "transition-shadow duration-200 hover:shadow-md" : "";
  const padding = "p-5";

  return (
    <div className={`${base} ${borderClass} ${hoverClass} ${padding} ${className}`}>
      {children}
    </div>
  );
}
