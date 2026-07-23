import { useState } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import Badge from '../common/Badge';
import StatusBadge from './StatusBadge';

const navItems = [
  { path: '/overview', label: '概览', icon: '⊞' },
  { path: '/sync', label: '同步', icon: '⟳' },
  { path: '/history', label: '历史', icon: '⧖' },
  { path: '/stats', label: '统计', icon: '⛶' },
  { path: '/forms', label: '表单', icon: '⊞' },
  { path: '/settings', label: '设置', icon: '⚙' },
  { path: '/diagnostics', label: '诊断', icon: '⚑' },
];

function Sidebar() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`fixed top-0 left-0 h-screen bg-ink text-paper flex flex-col transition-all duration-200 z-50 ${
        collapsed ? 'w-16' : 'w-56'
      }`}
    >
      {/* Logo area */}
      <div className="h-14 flex items-center px-4 border-b border-white/10">
        {!collapsed ? (
          <span className="text-sm font-bold tracking-tight text-paper">
            金蝶数据同步工具
          </span>
        ) : (
          <span className="text-lg font-bold text-paper">K</span>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 py-3 space-y-0.5 px-2 overflow-y-auto">
        {navItems.map(item => {
          const active =
            location.pathname === item.path ||
            (item.path !== '/history' && location.pathname.startsWith(item.path + '/'));
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `group flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive || active
                    ? 'bg-accent text-white font-medium'
                    : 'text-paper/70 hover:text-paper hover:bg-white/5'
                }`
              }
            >
              <span className="text-base leading-none">{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* Bottom area */}
      <div className="border-t border-white/10 p-3 space-y-2">
        <div className="flex items-center gap-2">
          <StatusBadge />
        </div>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-center py-1.5 text-xs text-paper/50 hover:text-paper transition-colors"
          title={collapsed ? '展开侧边栏' : '折叠侧边栏'}
        >
          {collapsed ? '→' : '← 折叠'}
        </button>
      </div>
    </aside>
  );
}

export default function Layout() {
  return (
    <div className="min-h-screen bg-paper">
      <Sidebar />
      <main className="ml-56 min-h-screen">
        <div className="max-w-7xl mx-auto px-8 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
