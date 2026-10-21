import {
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  Building2,
  ChevronDown,
  CircleHelp,
  Clock3,
  Download,
  FileText,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  ThumbsUp,
  TrendingUp,
  TriangleAlert,
  Users,
  X,
  Send,
  Check,
  Layers3,
} from "lucide-react";

const icons = {
  arrow: ArrowRight,
  external: ArrowUpRight,
  bookmark: Bookmark,
  building: Building2,
  chevron: ChevronDown,
  help: CircleHelp,
  clock: Clock3,
  download: Download,
  news: FileText,
  history: History,
  grid: LayoutDashboard,
  logout: LogOut,
  menu: Menu,
  chat: MessageSquare,
  refresh: RefreshCw,
  search: Search,
  filter: SlidersHorizontal,
  shield: ShieldCheck,
  spark: Sparkles,
  thumb: ThumbsUp,
  trend: TrendingUp,
  risk: TriangleAlert,
  user: Users,
  close: X,
  send: Send,
  check: Check,
  layers: Layers3,
};
export function Icon({ name, className = "", ...props }) {
  const Component = icons[name] || Sparkles;
  return (
    <Component
      size={19}
      strokeWidth={1.7}
      aria-hidden="true"
      className={`icon ${className}`}
      {...props}
    />
  );
}
export function Brand() {
  return (
    <a className="brand" href="#overview">
      <span className="alfa-mark">А</span>
      <span>
        Альфа<span className="brand-sub">Бизнес</span>
      </span>
    </a>
  );
}
export function Empty({
  title,
  children,
  action,
  label = "Попробовать ещё раз",
  icon = "search",
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon name={icon} size={28} />
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
      {action && (
        <button className="button secondary" onClick={action}>
          {label}
          <Icon name="arrow" />
        </button>
      )}
    </div>
  );
}
export function Loading({ label = "Загружаем события…" }) {
  return (
    <div className="loading-list" role="status" aria-label={label}>
      {[0, 1, 2].map((i) => (
        <div className="skeleton" key={i}>
          <i />
          <i />
          <i />
        </div>
      ))}
      <span className="sr-only">{label}</span>
    </div>
  );
}
export function SourceLink({ url, children }) {
  return url ? (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-button"
    >
      {children}
      <Icon name="external" />
    </a>
  ) : (
    <span className="muted">Внешняя ссылка не указана</span>
  );
}
