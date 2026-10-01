export default function Panel({ title, subtitle, children, className = '' }: {
  title?: string; subtitle?: string; children: React.ReactNode; className?: string
}) {
  return (
    <div className={`bg-tp-surface border border-tp-border rounded-md ${className}`}>
      {(title || subtitle) && (
        <div className="px-4 py-3 border-b border-tp-border">
          {title && <h3 className="text-sm font-semibold text-tp-text">{title}</h3>}
          {subtitle && <p className="text-xs text-tp-text-3 mt-0.5">{subtitle}</p>}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  )
}
