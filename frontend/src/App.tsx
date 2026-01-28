import { lazy } from 'react';
import { Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';

const RegionExplorer = lazy(async () => ({
  default: (await import('./pages/RegionExplorer')).RegionExplorer,
}));
const AnalysisView = lazy(async () => ({
  default: (await import('./pages/AnalysisView')).AnalysisView,
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
const Gallery = lazy(async () => ({
  default: (await import('./pages/Gallery')).Gallery,
}));
const AnimationStudio = lazy(async () => ({
  default: (await import('./pages/AnimationStudio')).AnimationStudio,
}));

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="regions" element={<RegionExplorer />} />
        <Route path="regions/:regionId" element={<AnalysisView />} />
        <Route path="analysis/:regionId" element={<AnalysisView />} />
        <Route path="map/:regionId" element={<MapPage />} />
        <Route path="compare/:regionId" element={<CompareView />} />
        <Route path="exports" element={<ExportCenter />} />
        <Route path="gallery" element={<Gallery />} />
        <Route path="animations" element={<AnimationStudio />} />
      </Route>
    </Routes>
  );
}

export default App;
