import { Suspense, lazy, useEffect, useRef } from 'react';
import {
  MapContainer as LeafletMapContainer,
  TileLayer,
  GeoJSON,
  useMap,
  useMapEvents,
  FeatureGroup,
} from 'react-leaflet';
import type { LatLngBounds, Map as LeafletMap } from 'leaflet';
import { shallow } from 'zustand/shallow';
import { useStore } from '../../store';
import type { Region, GeoJSONPolygon, MetricType } from '../../types';
import api from '../../services/api';
import { CompositeTileLayer } from './CompositeTileLayer';
import type { FlowPoint } from './FlowLayer';
import './MapContainer.css';

const METRIC_OVERLAY_MIN_ZOOM = 9;
const LazyFlowLayer = lazy(async () => ({
  default: (await import('./FlowLayer')).FlowLayer,
}));
const LazyEditControl = lazy(async () => ({
  default: (await import('react-leaflet-draw')).EditControl,
}));

interface MapContainerProps {
  regions?: Region[];
  onRegionSelect?: (region: Region) => void;
  onRegionCreate?: (geometry: GeoJSONPolygon) => void;
  showDrawControls?: boolean;
  selectedMetric?: MetricType;
  tileDate?: string; // Date for temporal tile data (YYYY-MM-DD)
  selectedRegion?: Region | null; // Optional prop to override store's selectedRegion
  flowPoints?: FlowPoint[]; // Optional migration flow visualization points
  flowColor?: string; // Color for flow particles
}

function MapController({
  focusRegion,
}: {
  focusRegion: Region | null;
}) {
  const map = useMap();
  const setMapCenter = useStore((state) => state.setMapCenter);
  const setMapZoom = useStore((state) => state.setMapZoom);

  useEffect(() => {
    if (focusRegion) {
      // Use geometry if available, otherwise use bounds
      if (focusRegion.geometry?.coordinates?.[0]) {
        const coords = focusRegion.geometry.coordinates[0];
        const lats = coords.map((c) => c[1]);
        const lngs = coords.map((c) => c[0]);
        const bounds: LatLngBounds = [
          [Math.min(...lats), Math.min(...lngs)],
          [Math.max(...lats), Math.max(...lngs)],
        ] as unknown as LatLngBounds;

        // Fit bounds to show the region - allow any zoom level
        // CompositeTileLayer will handle rendering z11 tiles at lower zoom levels
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 11, animate: false });

        // Sync store state immediately so zoom-gated overlays render on first load.
        const center = map.getCenter();
        setMapCenter([center.lat, center.lng]);
        setMapZoom(map.getZoom());
      }
    }
  }, [focusRegion, map, setMapCenter, setMapZoom]);

  return null;
}

function MapEvents() {
  const setMapCenter = useStore((state) => state.setMapCenter);
  const setMapZoom = useStore((state) => state.setMapZoom);

  useMapEvents({
    moveend: (e) => {
      const center = e.target.getCenter();
      setMapCenter([center.lat, center.lng]);
    },
    zoomend: (e) => {
      setMapZoom(e.target.getZoom());
    },
  });

  return null;
}

export function MapView({
  regions = [],
  onRegionSelect,
  onRegionCreate,
  showDrawControls = false,
  selectedMetric,
  tileDate,
  selectedRegion: selectedRegionProp,
  flowPoints,
  flowColor = '#3b82f6',
}: MapContainerProps) {
  const { mapState, storeSelectedRegion } = useStore(
    (state) => ({
      mapState: state.mapState,
      storeSelectedRegion: state.selectedRegion,
    }),
    shallow
  );
  const mapRef = useRef<LeafletMap | null>(null);

  // Use prop if provided, otherwise fall back to store
  const selectedRegion = selectedRegionProp !== undefined ? selectedRegionProp : storeSelectedRegion;
  const focusRegion = selectedRegion ?? (regions.length === 1 ? regions[0] : null);
  const showMetricOverlay = Boolean(selectedMetric && tileDate && mapState.zoom >= METRIC_OVERLAY_MIN_ZOOM);

  const handleCreated = (e: unknown) => {
    if (onRegionCreate) {
      const event = e as { layer: { toGeoJSON: () => { geometry: GeoJSONPolygon } } };
      const geoJson = event.layer.toGeoJSON();
      onRegionCreate(geoJson.geometry as GeoJSONPolygon);
    }
  };

  const getRegionStyle = (region: Region) => {
    const isSelected = selectedRegion?.id === region.id;
    return {
      color: isSelected ? '#2563eb' : '#64748b',
      weight: isSelected ? 3 : 2,
      fillColor: isSelected ? '#2563eb' : '#64748b',
      fillOpacity: isSelected ? 0.2 : 0.1,
    };
  };

  return (
    <div className="map-wrapper">
      <LeafletMapContainer
        center={mapState.center}
        zoom={mapState.zoom}
        minZoom={4}
        maxZoom={11}
        className="map-container"
        ref={mapRef}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* US-wide metric tile overlay - pre-generated tiles at z11 */}
        {/* CompositeTileLayer handles rendering at lower zoom levels by compositing z11 tiles */}
        {/* Nightlights and active_fire support daily (YYYY-MM-DD), others use monthly (YYYY-MM) */}
        {showMetricOverlay && selectedMetric && tileDate && (
          <CompositeTileLayer
            key={`us-${selectedMetric}-${tileDate}`}
            baseUrl={api.getUSTileUrl(
              selectedMetric,
              ['nightlights', 'active_fire'].includes(selectedMetric) ? tileDate : api.dateToYearMonth(tileDate)
            )}
            nativeZoom={11}
            minZoom={METRIC_OVERLAY_MIN_ZOOM}
            maxZoom={11}
            opacity={0.7}
          />
        )}

        {/* Region polygons - GeoJSON for regions with geometry */}
        {regions
          .filter((region) => region.geometry?.coordinates)
          .map((region) => (
            <GeoJSON
              key={region.id}
              data={region.geometry as GeoJSON.Geometry}
              style={() => getRegionStyle(region)}
              eventHandlers={{
                click: () => onRegionSelect?.(region),
              }}
            />
          ))}

        {/* Migration flow visualization */}
        {flowPoints && flowPoints.length > 0 && (
          <Suspense fallback={null}>
            <LazyFlowLayer
              points={flowPoints}
              color={flowColor}
              animated
              showLabels
              speed={1}
              particleCount={5}
            />
          </Suspense>
        )}

        {/* Draw controls */}
        {showDrawControls && (
          <FeatureGroup>
            <Suspense fallback={null}>
              <LazyEditControl
                position="topright"
                onCreated={handleCreated}
                draw={{
                  rectangle: false,
                  circle: false,
                  circlemarker: false,
                  marker: false,
                  polyline: false,
                  polygon: {
                    allowIntersection: false,
                    shapeOptions: {
                      color: '#2563eb',
                      fillColor: '#2563eb',
                      fillOpacity: 0.2,
                    },
                  },
                }}
                edit={{
                  edit: false,
                  remove: false,
                }}
              />
            </Suspense>
          </FeatureGroup>
        )}

        <MapController focusRegion={focusRegion} />
        <MapEvents />
      </LeafletMapContainer>

      {/* Map controls overlay */}
      <div className="map-controls">
        {!showMetricOverlay && selectedMetric && (
          <div className="map-overlay-hint">
            Zoom in to see overlay (z≥{METRIC_OVERLAY_MIN_ZOOM})
          </div>
        )}
        {selectedMetric && (
          <div className="map-legend">
            <span className="legend-title">{selectedMetric}</span>
            <div className="legend-gradient" data-metric={selectedMetric} />
            <div className="legend-labels">
              <span>Low</span>
              <span>High</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
