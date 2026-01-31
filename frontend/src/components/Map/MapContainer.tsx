import { Suspense, lazy, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
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
import type { Granularity, Region, GeoJSONPolygon, MetricType } from '../../types';
import api from '../../services/api';
import { METRIC_DEFAULT_GRANULARITY } from '../../config/metrics';
import { DEFAULT_METRIC_OVERLAY_MIN_ZOOM, MAX_MAP_ZOOM, MIN_MAP_ZOOM } from '../../config/map';
import { formatApiError } from '../../utils/errors';
import type { CompositeTileEvent } from './CompositeTileLayer';
import type { FlowPoint } from './FlowLayer';
import './MapContainer.css';

const MAPTILER_KEY = (import.meta.env.VITE_MAPTILER_KEY ?? '').trim();
const MAPTILER_OMT_RASTER_URL = `https://api.maptiler.com/maps/openstreetmap/{z}/{x}/{y}.png?key=${MAPTILER_KEY}`;

function clampZoom(zoom: number, min: number, max: number): number {
  if (!Number.isFinite(zoom)) return min;
  return Math.min(max, Math.max(min, zoom));
}

function toDateBucket(dateStr: string, granularity: Granularity): string {
  return granularity === 'monthly' ? dateStr.slice(0, 7) : dateStr.slice(0, 10);
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
  tileGranularity?: Granularity;
  overlayEnabled?: boolean;
  overlayAllowNetwork?: boolean;
  overlayMinZoom?: number;
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
  const mapContextRegionId = useStore((state) => state.mapState.contextRegionId);
  const updateMapState = useStore((state) => state.updateMapState);

  useEffect(() => {
    if (lockView) return;
    if (focusRegion) {
      if (mapContextRegionId === focusRegion.id) return;
      // Use geometry if available, otherwise use bounds
      if (focusRegion.geometry?.coordinates?.[0]) {
        const coords = focusRegion.geometry.coordinates[0];
        const lats = coords.map((c) => c[1]);
        const lngs = coords.map((c) => c[0]);
        const bounds: LatLngBounds = [
          [Math.min(...lats), Math.min(...lngs)],
          [Math.max(...lats), Math.max(...lngs)],
        ] as unknown as LatLngBounds;

        // Fit bounds to show the region.
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: MAX_MAP_ZOOM, animate: false });

        // Sync store state immediately so zoom-gated overlays render on first load.
        const center = map.getCenter();
        updateMapState({
          center: [center.lat, center.lng],
          zoom: map.getZoom(),
          contextRegionId: focusRegion.id,
        });
      }
    }
  }, [focusRegion, lockView, map, mapContextRegionId, updateMapState]);

  return null;
}

function MapEvents({ contextRegionId }: { contextRegionId: string | null }) {
  const updateMapState = useStore((state) => state.updateMapState);

  useMapEvents({
    moveend: (e) => {
      const center = e.target.getCenter();
      updateMapState({ center: [center.lat, center.lng], contextRegionId });
    },
    zoomend: (e) => {
      updateMapState({ zoom: e.target.getZoom(), contextRegionId });
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
  tileGranularity,
  overlayEnabled = true,
  overlayAllowNetwork = true,
  overlayMinZoom,
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

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    // Expose the Leaflet map instance for debugging / Playwright-driven checks.
    // react-leaflet assigns refs asynchronously; poll briefly until available.
    const handle = window.setInterval(() => {
      if (!mapRef.current) return;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).__satelliteLeafletMap = mapRef.current;
      window.clearInterval(handle);
    }, 50);
    return () => window.clearInterval(handle);
  }, []);

  // Use prop if provided, otherwise fall back to store
  const selectedRegion = selectedRegionProp !== undefined ? selectedRegionProp : storeSelectedRegion;
  const focusRegion = regions.length === 1 ? regions[0] : selectedRegion ?? null;
  const interactionContextRegionId =
    regions.length === 1
      ? regions[0].id
      : showDrawControls
        ? (selectedRegion?.id ?? null)
        : null;
  const effectiveOverlayMinZoom = clampZoom(
    typeof overlayMinZoom === 'number' ? Math.round(overlayMinZoom) : DEFAULT_METRIC_OVERLAY_MIN_ZOOM,
    MIN_MAP_ZOOM,
    MAX_MAP_ZOOM
  );
  const metricLayerMounted = Boolean(selectedMetric && tileDate);
  const metricLayerVisible = Boolean(
    overlayEnabled && overlayAllowNetwork && mapState.zoom >= effectiveOverlayMinZoom
  );

  const effectiveGranularity = selectedMetric
    ? (tileGranularity ?? METRIC_DEFAULT_GRANULARITY[selectedMetric])
    : undefined;
  const dateBucket =
    selectedMetric && tileDate && effectiveGranularity
      ? toDateBucket(tileDate, effectiveGranularity)
      : undefined;

  const {
    data: tileTemplate,
    isLoading: tileTemplateIsLoading,
    isError: tileTemplateIsError,
    error: tileTemplateError,
  } = useQuery({
    queryKey: ['tiles', 'template', selectedMetric, dateBucket, effectiveGranularity],
    queryFn: () =>
      api.getTileTemplate({
        metric: selectedMetric!,
        date_bucket: dateBucket!,
        granularity: effectiveGranularity!,
      }),
    // Prefetch the tile template as soon as we know the metric+date, so that when
    // the user zooms in past the cutoff the overlay appears immediately.
    enabled: Boolean(
      metricLayerMounted &&
        overlayEnabled &&
        overlayAllowNetwork &&
        selectedMetric &&
        dateBucket &&
        effectiveGranularity
    ),
    staleTime: 1000 * 60 * 60, // tokens are short-lived; keep cache bounded
  });

  const legendGradientStyle =
    tileTemplate?.palette?.length
      ? { background: `linear-gradient(to right, ${tileTemplate.palette.join(', ')})` }
      : undefined;

  const handleCreated = (e: unknown) => {
    if (onRegionCreate) {
      const event = e as { layer: { toGeoJSON: () => { geometry: GeoJSONPolygon } } };
      const geoJson = event.layer.toGeoJSON();
      onRegionCreate(geoJson.geometry as GeoJSONPolygon);
    }
  };

  const getRegionStyle = (region: Region) => {
    const isSelected = selectedRegion?.id === region.id;
    // Scale stroke width down when zoomed out so small regions don't collapse into thick, boxy markers.
    const zoomT =
      (mapState.zoom - MIN_MAP_ZOOM) / Math.max(1, MAX_MAP_ZOOM - MIN_MAP_ZOOM);
    const zoomScale = 0.25 + Math.min(1, Math.max(0, zoomT)) * 0.75;
    const baseWeight = isSelected ? 3 : 2;
    return {
      color: isSelected ? '#2563eb' : '#64748b',
      weight: baseWeight * zoomScale,
      fillColor: isSelected ? '#2563eb' : '#64748b',
      fillOpacity: 0,
    };
  };

  return (
    <div className="map-wrapper">
      <LeafletMapContainer
        center={mapState.center}
        zoom={mapState.zoom}
        minZoom={MIN_MAP_ZOOM}
        maxZoom={MAX_MAP_ZOOM}
        fadeAnimation={false}
        className="map-container"
        ref={mapRef}
      >
        <TileLayer
          attribution='<a href="https://www.maptiler.com/copyright/" target="_blank">&copy; MapTiler</a> <a href="https://www.openstreetmap.org/copyright" target="_blank">&copy; OpenStreetMap contributors</a>'
          url={MAPTILER_OMT_RASTER_URL}
          tileSize={512}
          zoomOffset={-1}
          crossOrigin
        />

        {/* Metric tile overlay (Earth Engine URL template) */}
        {metricLayerMounted && metricLayerVisible && tileTemplate?.tile_url && (
          <TileLayer
            key={`${tileTemplate.metric}:${tileTemplate.granularity}:${tileTemplate.date_bucket}`}
            url={tileTemplate.tile_url}
            opacity={tileTemplate.opacity}
            attribution={tileTemplate.attribution ?? undefined}
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
                      fillOpacity: 0,
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
        <MapEvents contextRegionId={interactionContextRegionId} />
      </LeafletMapContainer>

      {/* Map controls overlay */}
      <div className="map-controls">
        {overlayEnabled && selectedMetric && mapState.zoom < effectiveOverlayMinZoom && (
          <div className="map-overlay-hint">
            Zoom in to see overlay (z≥{effectiveOverlayMinZoom})
          </div>
        )}
        {overlayEnabled && selectedMetric && metricLayerMounted && metricLayerVisible && tileTemplateIsLoading && (
          <div className="map-overlay-hint">Loading overlay…</div>
        )}
        {overlayEnabled && selectedMetric && metricLayerMounted && metricLayerVisible && tileTemplateIsError && (
          <div className="map-overlay-hint">
            Overlay failed to load: {formatApiError(tileTemplateError)}
          </div>
        )}
        {overlayEnabled &&
          selectedMetric &&
          metricLayerMounted &&
          metricLayerVisible &&
          !tileTemplateIsLoading &&
          !tileTemplateIsError &&
          !tileTemplate?.tile_url && (
            <div className="map-overlay-hint">No overlay available for this metric/date.</div>
          )}
        {selectedMetric && (
          <div className="map-legend">
            <span className="legend-title">{selectedMetric}</span>
            <div
              className="legend-gradient"
              data-metric={selectedMetric}
              style={legendGradientStyle}
            />
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
