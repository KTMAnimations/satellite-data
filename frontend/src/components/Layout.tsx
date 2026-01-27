import { Suspense } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import {
  SquaresFour,
  MapTrifold,
  FilmStrip,
  DownloadSimple,
  Images,
  List,
  Planet,
} from '@phosphor-icons/react';
import { useStore } from '../store';
import './Layout.css';

export function Layout() {
  const location = useLocation();
  const { sidebarOpen, setSidebarOpen } = useStore();

  const navItems = [
    { path: '/', label: 'Dashboard', icon: SquaresFour },
    { path: '/regions', label: 'Regions', icon: MapTrifold },
    { path: '/animations', label: 'Animations', icon: FilmStrip },
    { path: '/exports', label: 'Exports', icon: DownloadSimple },
    { path: '/gallery', label: 'Gallery', icon: Images },
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
            <List size={20} weight="bold" />
          </button>
          <Link to="/" className="logo">
            <div className="logo-icon">
              <Planet size={22} weight="duotone" />
            </div>
            <span className="logo-text">SatelliteMigration</span>
          </Link>
        </div>

        <nav className={`header-nav ${sidebarOpen ? 'open' : ''}`}>
          <div className="nav-section">
            {navItems.map((item, index) => {
              const Icon = item.icon;
              return (
                <div key={item.path} className="nav-item">
                  {index > 0 && <div className="nav-divider" />}
                  <Link
                    to={item.path}
                    className={`nav-link ${location.pathname === item.path ? 'active' : ''}`}
                  >
                    <Icon size={16} weight={location.pathname === item.path ? 'fill' : 'regular'} />
                    <span className="nav-label">{item.label}</span>
                  </Link>
                </div>
              );
            })}
          </div>
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
        <Suspense fallback={<div className="loading">Loading...</div>}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
}
