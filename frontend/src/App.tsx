import { Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { RegionExplorer } from './pages/RegionExplorer';
import { AnalysisView } from './pages/AnalysisView';
import { ExportCenter } from './pages/ExportCenter';
import { Gallery } from './pages/Gallery';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="regions" element={<RegionExplorer />} />
        <Route path="regions/:regionId" element={<AnalysisView />} />
        <Route path="analysis/:regionId" element={<AnalysisView />} />
        <Route path="exports" element={<ExportCenter />} />
        <Route path="gallery" element={<Gallery />} />
      </Route>
    </Routes>
  );
}

export default App;
