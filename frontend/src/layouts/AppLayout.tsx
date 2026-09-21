import { NavLink, Outlet } from "react-router-dom";
import {
  FileText,
  Files,
  ArrowLeftRight,
  Zap,
  HomeIcon,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { Logo } from "@/components/Logo";
import { useApp } from "@/context/AppContext";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/", label: "Home", icon: HomeIcon, end: true },
  { to: "/documents", label: "Documents", icon: FileText },
  { to: "/analyze", label: "Analyze", icon: Zap },
  { to: "/compare", label: "Compare", icon: ArrowLeftRight },
  { to: "/action-pack", label: "Action Pack", icon: Files },
];

export function AppLayout() {
  const { workspaceId, setWorkspaceId } = useApp();

  return (
    <div className="flex h-full min-h-screen">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="px-5 pb-2 pt-6">
          <Logo />
        </div>
        <nav className="mt-4 flex-1 space-y-1 px-3">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-brand-50 text-brand-700"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
                )
              }
            >
              <item.icon className="h-[18px] w-[18px]" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="space-y-1 border-t border-slate-100 px-3 py-3">
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-50",
              )
            }
          >
            <Settings className="h-[18px] w-[18px]" />
            Settings
          </NavLink>
          <div className="flex items-center gap-2 px-3 pt-1 text-[11px] text-slate-400">
            <ShieldCheck className="h-3.5 w-3.5" />
            Grounded · Evidence-backed
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 lg:px-6">
          <div className="flex items-center gap-2 lg:hidden">
            <Logo mark="" />
          </div>
          <div className="flex flex-1 items-center gap-2">
            <span className="hidden text-xs text-slate-400 sm:inline">Workspace</span>
            <input
              value={workspaceId}
              onChange={(e) => setWorkspaceId(e.target.value.trim() || "public")}
              className="input w-40 !py-1.5 text-xs sm:w-52"
              placeholder="public"
            />
          </div>
        </header>
        <nav className="flex shrink-0 gap-1 overflow-x-auto border-b border-slate-100 bg-white px-2 lg:hidden">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-1.5 whitespace-nowrap px-3 py-2.5 text-xs font-medium",
                  isActive ? "border-b-2 border-brand-500 text-brand-700" : "text-slate-500",
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}