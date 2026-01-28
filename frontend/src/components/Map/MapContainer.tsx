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
import type { CompositeTileEvent } from './CompositeTileLayer';
import type { FlowPoint } from './FlowLayer';
import './MapContainer.css';

const METRIC_OVERLAY_MIN_ZOOM = 9;
const US_BOUNDS_4326 = { west: -125.0, east: -66.0, south: 24.0, north: 50.0 };

function getPolygonBounds(geometry: GeoJSONPolygon | null | undefined): {
  west: number;
  south: number;
  east: number;
  north: number;
} | null {
  const ring = geometry?.coordinates?.[0];
  if (!ring || ring.length === 0) return null;

  let west = Number.POSITIVE_INFINITY;
  let south = Number.POSITIVE_INFINITY;
  let east = Number.NEGATIVE_INFINITY;
  let north = Number.NEGATIVE_INFINITY;

  for (const [lon, lat] of ring) {
    west = Math.min(west, lon);
    south = Math.min(south, lat);
    east = Math.max(east, lon);
    north = Math.max(north, lat);
  }

  if (!Number.isFinite(west) || !Number.isFinite(south) || !Number.isFinite(east) || !Number.isFinite(north)) {
    return null;
  }

  return { west, south, east, north };
}

function intersectsBounds(
  a: { west: number; south: number; east: number; north: number },
  b: { west: number; south: number; east: number; north: number }
): boolean {
  return !(a.east < b.west || a.west > b.east || a.north < b.south || a.south > b.north);
}

function regionLikelyInUS(region: Region | null): boolean {
  if (!region) return true; // Preserve legacy behavior if no region context
  if (region.country?.toUpperCase() === 'USA') return true;

  const bounds = getPolygonBounds(region.geometry);
  if (!bounds) return false;
  return intersectsBounds(bounds, US_BOUNDS_4326);
}

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
  overlayEnabled?: boolean;
  overlayAllowNetwork?: boolean;
  onOverlayTileEvent?: (event: CompositeTileEvent) => void;
  viewLocked?: boolean;
  selectedRegion?: Region | null; // Optional prop to override store's selectedRegion
  flowPoints?: FlowPoint[]; // Optional migration flow visualization points
  flowColor?: string; // Color for flow particles
}

function MapInteractionLock({ locked }: { locked: boolean }) {
  const map = useMap();

  useEffect(() => {
    if (!map) return;

    if (locked) {
      map.dragging.disable();
      map.scrollWheelZoom.disable();
      map.doubleClickZoom.disable();
      map.boxZoom.disable();
      map.keyboard.disable();
      map.touchZoom.disable();

      // Leaflet tap handler exists only on some devices/builds.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (map as any).tap?.disable?.();
      return;
    }

    map.dragging.enable();
    map.scrollWheelZoom.enable();
    map.doubleClickZoom.enable();
    map.boxZoom.enable();
    map.keyboard.enable();
    map.touchZoom.enable();

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (map as any).tap?.enable?.();
  }, [map, locked]);

  return null;
}

function MapController({
  focusRegion,
  lockView,
}: {
  focusRegion: Region | null;
  lockView: boolean;
}) {
  const map = useMap();
  const setMapCenter = useStore((state) => state.setMapCenter);
  const setMapZoom = useStore((state) => state.setMapZoom);

  useEffect(() => {
    if (lockView) return;
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
  }, [focusRegion, lockView, map, setMapCenter, setMapZoom]);

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
  overlayEnabled = true,
  overlayAllowNetwork = true,
  onOverlayTileEvent,
  viewLocked = false,
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
  const metricLayerMounted = Boolean(selectedMetric && tileDate);
  const metricLayerVisible = Boolean(overlayEnabled && mapState.zoom >= METRIC_OVERLAY_MIN_ZOOM);
  const metricTileBucket =
    selectedMetric && tileDate
      ? ['nightlights', 'active_fire'].includes(selectedMetric)
        ? tileDate
        : api.dateToYearMonth(tileDate)
      : undefined;
  const useUsTiles = regionLikelyInUS(focusRegion);

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

        {/* Metric tile overlay - z11 tiles composited down for lower zooms */}
        {/* CompositeTileLayer handles rendering at lower zoom levels by compositing z11 tiles */}
        {/* Nightlights and active_fire support daily (YYYY-MM-DD), others use monthly (YYYY-MM) */}
        {metricLayerMounted && selectedMetric && tileDate && (
          <CompositeTileLayer
            baseUrl={
              useUsTiles
                ? api.getUSTileUrl(selectedMetric, metricTileBucket!)
                : api.getWorldTileUrl(selectedMetric, metricTileBucket!)
            }
            nativeZoom={11}
            minZoom={METRIC_OVERLAY_MIN_ZOOM}
            maxZoom={11}
            opacity={0.7}
            enabled={metricLayerVisible}
            allowNetwork={overlayAllowNetwork}
            onTileEvent={onOverlayTileEvent}
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

        <MapInteractionLock locked={viewLocked} />
        <MapController focusRegion={focusRegion} lockView={viewLocked} />
        <MapEvents />
      </LeafletMapContainer>

      {/* Map controls overlay */}
      <div className="map-controls">
        {overlayEnabled && selectedMetric && mapState.zoom < METRIC_OVERLAY_MIN_ZOOM && (
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
