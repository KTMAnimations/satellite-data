import { useEffect, useMemo, useState, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { UploadSimple } from '@phosphor-icons/react';
import { MapView } from '../components/Map/MapContainer';
import { useStore } from '../store';
import api from '../services/api';
import { formatApiError } from '../utils/errors';
import type { Region, GeoJSONPolygon } from '../types';
import './RegionExplorer.css';

export function RegionExplorer() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { selectedRegion, setSelectedRegion, setSelectedMetrics, setDateRange } = useStore();

  const presetId = searchParams.get('preset');

  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState<string>('');
  const [filterCategory, setFilterCategory] = useState<string>('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newRegionName, setNewRegionName] = useState('');
  const [newRegionGeometry, setNewRegionGeometry] = useState<GeoJSONPolygon | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: preset, isLoading: presetLoading, isError: presetIsError, error: presetError } = useQuery({
    queryKey: ['preset', presetId],
    queryFn: ({ signal }) => api.getPreset(presetId!, { signal }),
    enabled: !!presetId,
  });

  useEffect(() => {
    if (!preset) return;

    setSelectedMetrics(preset.metrics);
    if (preset.date_range) {
      setDateRange({
        start: new Date(preset.date_range.start_date),
        end: new Date(preset.date_range.end_date),
      });
    }
  }, [preset, setDateRange, setSelectedMetrics]);

  const listParams = presetId
    ? { page_size: 200 }
    : {
        search: searchTerm || undefined,
        type: filterType || undefined,
        category: filterCategory || undefined,
        page_size: 100,
      };

  const { data: regionsData, isLoading, isError: regionsIsError, error: regionsError } = useQuery({
    queryKey: ['regions', listParams],
    queryFn: ({ signal }) => api.listRegions(listParams, { signal }),
  });

  const visibleRegions = useMemo(() => {
    let regions = regionsData?.regions ?? [];

    if (preset) {
      const ids = new Set(preset.regions.flatMap((r) => (r.region_id ? [r.region_id] : [])));
      regions = regions.filter((r) => ids.has(r.id));
    }

    if (searchTerm) {
      const needle = searchTerm.toLowerCase();
      regions = regions.filter((r) => r.name.toLowerCase().includes(needle));
    }
    if (filterType) {
      regions = regions.filter((r) => r.type === filterType);
    }
    if (filterCategory) {
      regions = regions.filter((r) => r.category === filterCategory);
    }

    return regions;
  }, [preset, regionsData, searchTerm, filterCategory, filterType]);

  const createRegionMutation = useMutation({
    mutationFn: (data: { name: string; geometry: GeoJSONPolygon }) =>
      api.createRegion(data),
    onSuccess: (region) => {
      queryClient.invalidateQueries({ queryKey: ['regions'] });
      setShowCreateModal(false);
      setNewRegionName('');
      setNewRegionGeometry(null);
      setCreateError(null);
      setSelectedRegion(region);
      navigate(`/regions/${region.id}`);
    },
    onError: (err) => {
      setCreateError(formatApiError(err));
    },
  });

  const handleRegionSelect = (region: Region) => {
    setSelectedRegion(region);
  };

  const handleRegionCreate = (geometry: GeoJSONPolygon) => {
    setNewRegionGeometry(geometry);
    setShowCreateModal(true);
    setCreateError(null);
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

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploadError(null);
    const reader = new FileReader();

    reader.onload = (e) => {
      try {
        const content = e.target?.result as string;
        const geojson = JSON.parse(content);

        // Extract geometry from GeoJSON
        let geometry: GeoJSONPolygon | null = null;

        if (geojson.type === 'FeatureCollection' && geojson.features?.length > 0) {
          const feature = geojson.features[0];
          if (feature.geometry?.type === 'Polygon') {
            geometry = feature.geometry as GeoJSONPolygon;
          } else if (feature.geometry?.type === 'MultiPolygon') {
            // Convert first polygon of MultiPolygon
            geometry = {
              type: 'Polygon',
              coordinates: feature.geometry.coordinates[0],
            };
          }
        } else if (geojson.type === 'Feature' && geojson.geometry) {
          if (geojson.geometry.type === 'Polygon') {
            geometry = geojson.geometry as GeoJSONPolygon;
          } else if (geojson.geometry.type === 'MultiPolygon') {
            geometry = {
              type: 'Polygon',
              coordinates: geojson.geometry.coordinates[0],
            };
          }
        } else if (geojson.type === 'Polygon') {
          geometry = geojson as GeoJSONPolygon;
        }

        if (geometry) {
          // Use filename without extension as default name
          const defaultName = file.name.replace(/\.(geo)?json$/i, '');
          setNewRegionName(defaultName);
          setNewRegionGeometry(geometry);
          setShowCreateModal(true);
          setCreateError(null);
        } else {
          setUploadError('Could not find a valid Polygon geometry in the file');
        }
      } catch {
        setUploadError('Invalid GeoJSON file. Please check the format.');
      }
    };

    reader.onerror = () => {
      setUploadError('Error reading file');
    };

    reader.readAsText(file);
    // Reset input so same file can be uploaded again
    event.target.value = '';
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
          {presetId && (
            <div className="preset-banner">
              <div className="preset-banner-text">
                <strong>Preset:</strong>{' '}
                {presetLoading
                  ? 'Loading…'
                  : presetIsError
                    ? `Error: ${formatApiError(presetError)}`
                    : preset?.name ?? presetId}
              </div>
              <button
                className="btn btn-outline"
                onClick={() => {
                  navigate('/regions');
                }}
              >
                Clear
              </button>
            </div>
          )}

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

          {/* GeoJSON Upload */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".json,.geojson"
            style={{ display: 'none' }}
          />
          <button
            className="btn btn-outline upload-btn"
            onClick={() => fileInputRef.current?.click()}
          >
            <UploadSimple size={16} weight="bold" />
            Upload GeoJSON
          </button>
          {uploadError && <div className="upload-error">{uploadError}</div>}
        </div>

        {/* Region List */}
        <div className="region-list">
          {isLoading ? (
            <div className="loading">Loading regions...</div>
          ) : regionsIsError ? (
            <div className="loading">Error loading regions: {formatApiError(regionsError)}</div>
          ) : (
            visibleRegions.map((region) => (
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
          regions={visibleRegions}
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
        <div
          className="modal-overlay"
          onClick={() => {
            setShowCreateModal(false);
            setCreateError(null);
          }}
        >
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

            {createError && <div className="upload-error">{createError}</div>}

            <div className="modal-actions">
              <button
                className="btn btn-outline"
                onClick={() => {
                  setShowCreateModal(false);
                  setNewRegionGeometry(null);
                  setCreateError(null);
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
