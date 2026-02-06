import { lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';

const RegionExplorer = lazy(async () => ({
  default: (await import('./pages/RegionExplorer')).RegionExplorer,
}));
const AnalysisView = lazy(async () => ({
  default: (await import('./pages/AnalysisView')).AnalysisView,
}));
const FullMapPage = lazy(async () => ({
  default: (await import('./pages/FullMapPage')).FullMapPage,
}));
const MapPage = lazy(async () => ({
  default: (await import('./pages/MapPage')).MapPage,
}));
const CompareView = lazy(async () => ({
  default: (await import('./pages/CompareView')).CompareView,
}));
const ExportCenter = lazy(async () => ({
  default: (await import('./pages/ExportCenter')).ExportCenter,
}));

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/map" replace />} />
        <Route path="map" element={<FullMapPage />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="regions" element={<RegionExplorer />} />
        <Route path="regions/:regionId" element={<AnalysisView />} />
        <Route path="analysis/:regionId" element={<AnalysisView />} />
        <Route path="map/:regionId" element={<MapPage />} />
        <Route path="compare/:regionId" element={<CompareView />} />
        <Route path="exports" element={<ExportCenter />} />
      </Route>
    </Routes>
  );
}

export default App;
