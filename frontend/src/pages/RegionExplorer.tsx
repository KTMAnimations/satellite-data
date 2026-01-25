import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { MapView } from '../components/Map/MapContainer';
import { useStore } from '../store';
import api from '../services/api';
import type { Region, GeoJSONPolygon } from '../types';
import './RegionExplorer.css';

export function RegionExplorer() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { selectedRegion, setSelectedRegion } = useStore();

  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState<string>('');
  const [filterCategory, setFilterCategory] = useState<string>('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newRegionName, setNewRegionName] = useState('');
  const [newRegionGeometry, setNewRegionGeometry] = useState<GeoJSONPolygon | null>(null);

  const { data: regionsData, isLoading } = useQuery({
    queryKey: ['regions', { search: searchTerm, type: filterType, category: filterCategory }],
    queryFn: () =>
      api.listRegions({
        search: searchTerm || undefined,
        type: filterType || undefined,
        category: filterCategory || undefined,
        page_size: 100,
      }),
  });

  const createRegionMutation = useMutation({
    mutationFn: (data: { name: string; geometry: GeoJSONPolygon }) =>
      api.createRegion(data),
    onSuccess: (region) => {
      queryClient.invalidateQueries({ queryKey: ['regions'] });
      setShowCreateModal(false);
      setNewRegionName('');
      setNewRegionGeometry(null);
      setSelectedRegion(region);
      navigate(`/regions/${region.id}`);
    },
  });

  const handleRegionSelect = (region: Region) => {
    setSelectedRegion(region);
  };

  const handleRegionCreate = (geometry: GeoJSONPolygon) => {
    setNewRegionGeometry(geometry);
    setShowCreateModal(true);
  };

  const handleCreateSubmit = () => {
    if (newRegionName && newRegionGeometry) {
      createRegionMutation.mutate({
        name: newRegionName,
        geometry: newRegionGeometry,
      });
    }
  };

  const handleViewAnalysis = () => {
    if (selectedRegion) {
      navigate(`/analysis/${selectedRegion.id}`);
    }
  };

  return (
    <div className="region-explorer">
      <aside className="region-sidebar">
        <div className="sidebar-header">
          <h2>Regions</h2>
          <p>Select a region to analyze or draw a custom area</p>
        </div>

        {/* Filters */}
        <div className="sidebar-filters">
          <input
            type="text"
            placeholder="Search regions..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />

          <div className="filter-row">
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="filter-select"
            >
              <option value="">All Types</option>
              <option value="predefined">Predefined</option>
              <option value="custom">Custom</option>
            </select>

            <select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              className="filter-select"
            >
              <option value="">All Categories</option>
              <option value="major_city">Major Cities</option>
              <option value="megacity">Megacities</option>
              <option value="migration_hotspot">Migration Hotspots</option>
            </select>
          </div>
        </div>

        {/* Region List */}
        <div className="region-list">
          {isLoading ? (
            <div className="loading">Loading regions...</div>
          ) : (
            regionsData?.regions.map((region) => (
              <div
                key={region.id}
                className={`region-item ${selectedRegion?.id === region.id ? 'selected' : ''}`}
                onClick={() => handleRegionSelect(region)}
              >
                <div className="region-item-header">
                  <span className="region-name">{region.name}</span>
                  <span className={`region-type ${region.type}`}>{region.type}</span>
                </div>
                {region.country && (
                  <span className="region-location">
                    {region.state_province ? `${region.state_province}, ` : ''}
                    {region.country}
                  </span>
                )}
                {region.category && (
                  <span className="region-category">{region.category.replace('_', ' ')}</span>
                )}
              </div>
            ))
          )}
        </div>

        {/* Selected Region Actions */}
        {selectedRegion && (
          <div className="sidebar-actions">
            <button className="btn btn-primary" onClick={handleViewAnalysis}>
              View Analysis
            </button>
            {selectedRegion.type === 'custom' && (
              <button
                className="btn btn-outline"
                onClick={() => {
                  if (confirm('Delete this region?')) {
                    api.deleteRegion(selectedRegion.id).then(() => {
                      queryClient.invalidateQueries({ queryKey: ['regions'] });
                      setSelectedRegion(null);
                    });
                  }
                }}
              >
                Delete
              </button>
            )}
          </div>
        )}
      </aside>

      <main className="region-map-area">
        <MapView
          regions={regionsData?.regions || []}
          onRegionSelect={handleRegionSelect}
          onRegionCreate={handleRegionCreate}
          showDrawControls={true}
        />

        {/* Instructions */}
        <div className="map-instructions">
          <span>Click a region to select it, or use the polygon tool to draw a custom area</span>
        </div>
      </main>

      {/* Create Region Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Create Custom Region</h3>
            <p>Give your region a name to save it for analysis.</p>

            <input
              type="text"
              placeholder="Region name"
              value={newRegionName}
              onChange={(e) => setNewRegionName(e.target.value)}
              className="input"
              autoFocus
            />

            <div className="modal-actions">
              <button
                className="btn btn-outline"
                onClick={() => {
                  setShowCreateModal(false);
                  setNewRegionGeometry(null);
                }}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleCreateSubmit}
                disabled={!newRegionName || createRegionMutation.isPending}
              >
                {createRegionMutation.isPending ? 'Creating...' : 'Create Region'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
