import { Suspense, useEffect } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import {
  GlobeHemisphereWest,
  MapTrifold,
  DownloadSimple,
  List,
} from '@phosphor-icons/react';
import { shallow } from 'zustand/shallow';
import { useStore, type NavSection } from '../store';
import { ErrorBoundary } from './ErrorBoundary';
import exeterSeal from '../assets/exeter-seal.png';
import './Layout.css';

function navSectionForPath(pathname: string): NavSection {
  if (pathname === '/' || pathname === '/map') return 'fullmap';
  if (
    pathname.startsWith('/regions')
    || pathname.startsWith('/analysis')
    || pathname.startsWith('/map/')
    || pathname.startsWith('/compare')
  ) {
    return 'regions';
  }
  if (pathname.startsWith('/dashboard')) return 'dashboard';
  if (pathname.startsWith('/exports')) return 'exports';
  return 'fullmap';
}

export function Layout() {
  const location = useLocation();
  const { sidebarOpen, setSidebarOpen, navLastPath, setNavLastPath } = useStore(
    (state) => ({
      sidebarOpen: state.sidebarOpen,
      setSidebarOpen: state.setSidebarOpen,
      navLastPath: state.navLastPath,
      setNavLastPath: state.setNavLastPath,
    }),
    shallow
  );

  const navItems = [
    { section: 'fullmap' as const, path: '/map', label: 'Full Map', icon: GlobeHemisphereWest },
    { section: 'regions' as const, path: '/regions', label: 'Regions', icon: MapTrifold },
    { section: 'exports' as const, path: '/exports', label: 'Exports', icon: DownloadSimple },
  ];

  const activeSection = navSectionForPath(location.pathname);

  useEffect(() => {
    const section = navSectionForPath(location.pathname);
    const fullPath = `${location.pathname}${location.search}`;
    if (navLastPath[section] === fullPath) return;
    setNavLastPath(section, fullPath);
  }, [location.pathname, location.search, navLastPath, setNavLastPath]);

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
              <img src={exeterSeal} alt="" className="logo-seal" aria-hidden="true" />
            </div>
            <span className="logo-text">Exeter Astro</span>
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
                    to={navLastPath[item.section] ?? item.path}
                    className={`nav-link ${activeSection === item.section ? 'active' : ''}`}
                  >
                    <Icon size={16} weight={activeSection === item.section ? 'fill' : 'regular'} />
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
        <ErrorBoundary>
          <Suspense fallback={<div className="loading">Loading...</div>}>
            <Outlet />
          </Suspense>
        </ErrorBoundary>
      </main>
    </div>
  );
}
