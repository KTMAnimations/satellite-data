import { Outlet, Link, useLocation } from 'react-router-dom';
import { useStore } from '../store';
import './Layout.css';

export function Layout() {
  const location = useLocation();
  const { sidebarOpen, setSidebarOpen } = useStore();

  const navItems = [
    { path: '/', label: 'Dashboard', icon: '📊' },
    { path: '/regions', label: 'Regions', icon: '🗺️' },
    { path: '/exports', label: 'Exports', icon: '📥' },
    { path: '/gallery', label: 'Gallery', icon: '🖼️' },
  ];

  return (
    <div className="layout">
      <header className="header">
        <div className="header-left">
          <button
            className="menu-toggle"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Toggle sidebar"
          >
            ☰
          </button>
          <Link to="/" className="logo">
            <span className="logo-icon">🛰️</span>
            <span className="logo-text">SatelliteMigration</span>
          </Link>
        </div>
        <nav className="header-nav">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`nav-link ${location.pathname === item.path ? 'active' : ''}`}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
            </Link>
          ))}
        </nav>
        <div className="header-right">
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="header-link"
          >
            Docs
          </a>
        </div>
      </header>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
