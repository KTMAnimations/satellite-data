import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import type { Granularity, MapState, Region, GeoJSONPolygon, MetricType, TileTemplateResponse } from '../../types';
import api from '../../services/api';
import { telemetry } from '../../services/telemetry';
import { METRIC_DEFAULT_GRANULARITY } from '../../config/metrics';
import { MAX_MAP_ZOOM, MIN_MAP_ZOOM } from '../../config/map';
import { formatApiError } from '../../utils/errors';
import type { CompositeTileEvent } from './CompositeTileLayer';
import type { FlowPoint } from './FlowLayer';
import { AbortableTileLayer } from './AbortableTileLayer';
import './MapContainer.css';

const MAPTILER_KEY = (import.meta.env.VITE_MAPTILER_KEY ?? '').trim();
const MAPTILER_OMT_RASTER_URL = `https://api.maptiler.com/maps/openstreetmap/{z}/{x}/{y}.png?key=${MAPTILER_KEY}`;
const CARTO_DARK_RASTER_URL = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png';
const CARTO_DARK_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors ' +
  '&copy; <a href="https://carto.com/attributions" target="_blank" rel="noreferrer">CARTO</a>';

function toDateBucket(dateStr: string, granularity: Granularity): string {
  return granularity === 'monthly' ? dateStr.slice(0, 7) : dateStr.slice(0, 10);
}

function withCacheBust(tileUrl: string, cacheBustKey?: string | number): string {
  if (cacheBustKey === undefined || cacheBustKey === null || cacheBustKey === '') return tileUrl;
  const sep = tileUrl.includes('?') ? '&' : '?';
  return `${tileUrl}${sep}cb=${encodeURIComponent(String(cacheBustKey))}`;
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
  tileCacheBustKey?: string | number;
  overlayEnabled?: boolean;
  overlayAllowNetwork?: boolean;
  onOverlayLoadingChange?: (isLoading: boolean) => void;
  onOverlayTileEvent?: (event: CompositeTileEvent) => void;
  viewLocked?: boolean;
  selectedRegion?: Region | null; // Optional prop to override store's selectedRegion
  flowPoints?: FlowPoint[]; // Optional migration flow visualization points
  flowColor?: string; // Color for flow particles
  onMapReady?: (map: LeafletMap | null) => void;
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

        // Sync store state immediately after fitBounds.
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
  const pendingRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const patchRef = useRef<Partial<MapState>>({});

  // Flush any pending debounced update on unmount.
  useEffect(() => {
    return () => {
      if (pendingRef.current) {
        clearTimeout(pendingRef.current);
        updateMapState({ ...patchRef.current, contextRegionId });
        pendingRef.current = null;
        patchRef.current = {};
      }
    };
  }, [updateMapState, contextRegionId]);

  useMapEvents({
    moveend: (e) => {
      const center = e.target.getCenter();
      patchRef.current = { ...patchRef.current, center: [center.lat, center.lng] };
      if (pendingRef.current) clearTimeout(pendingRef.current);
      pendingRef.current = setTimeout(() => {
        updateMapState({ ...patchRef.current, contextRegionId });
        patchRef.current = {};
        pendingRef.current = null;
      }, 150);
    },
    zoomend: (e) => {
      const center = e.target.getCenter();
      telemetry.log('map_zoom', {
        center: [center.lat, center.lng],
        zoom: e.target.getZoom(),
        contextRegionId,
      });
      patchRef.current = { ...patchRef.current, zoom: e.target.getZoom() };
      if (pendingRef.current) clearTimeout(pendingRef.current);
      pendingRef.current = setTimeout(() => {
        updateMapState({ ...patchRef.current, contextRegionId });
        patchRef.current = {};
        pendingRef.current = null;
      }, 150);
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
  tileCacheBustKey,
  overlayEnabled = true,
  overlayAllowNetwork = true,
  onOverlayLoadingChange,
  viewLocked = false,
  selectedRegion: selectedRegionProp,
  flowPoints,
  flowColor = '#3b82f6',
  onMapReady,
}: MapContainerProps) {
  const { mapState, storeSelectedRegion } = useStore(
    (state) => ({
      mapState: state.mapState,
      storeSelectedRegion: state.selectedRegion,
    }),
    shallow
  );
  const mapRef = useRef<LeafletMap | null>(null);
  const [mapContainerEl, setMapContainerEl] = useState<HTMLElement | null>(null);

  const handleMapRef = useCallback(
    (map: LeafletMap | null) => {
      mapRef.current = map;
      setMapContainerEl(map ? map.getContainer() : null);
      if (import.meta.env.DEV && map) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (window as any).__satelliteLeafletMap = map;
      }
      onMapReady?.(map);
    },
    [onMapReady]
  );

  // Use prop if provided, otherwise fall back to store
  const selectedRegion = selectedRegionProp !== undefined ? selectedRegionProp : storeSelectedRegion;
  const focusRegion = regions.length === 1 ? regions[0] : selectedRegion ?? null;
  const interactionContextRegionId =
    regions.length === 1
      ? regions[0].id
      : showDrawControls
        ? (selectedRegion?.id ?? null)
        : null;
  const useDarkBasemap = selectedMetric === 'nightlights';
  const metricLayerMounted = Boolean(selectedMetric && tileDate);
  const metricLayerVisible = Boolean(overlayEnabled && overlayAllowNetwork);

  useEffect(() => {
    if (!mapContainerEl) return;
    mapContainerEl.classList.toggle('map-container--dark', useDarkBasemap);
    return () => {
      mapContainerEl.classList.remove('map-container--dark');
    };
  }, [mapContainerEl, useDarkBasemap]);

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
    isFetching: tileTemplateIsFetching,
    isError: tileTemplateIsError,
    error: tileTemplateError,
  } = useQuery({
    queryKey: ['tiles', 'template', selectedMetric, dateBucket, effectiveGranularity],
    queryFn: ({ signal }) =>
      api.getTileTemplate({
        metric: selectedMetric!,
        date_bucket: dateBucket!,
        granularity: effectiveGranularity!,
      }, { signal }),
    // Prefetch the tile template as soon as we know the metric+date, so that when
    // the overlay becomes visible it appears immediately.
    enabled: Boolean(
      metricLayerMounted &&
        overlayEnabled &&
        overlayAllowNetwork &&
        selectedMetric &&
        dateBucket &&
        effectiveGranularity
    ),
    // Avoid a blank frame while switching dates by keeping the last successful template
    // for the same metric/granularity until the next one is available.
    placeholderData: (previousData) => {
      if (!previousData) return previousData;
      if (!selectedMetric || !effectiveGranularity) return undefined;
      if (previousData.metric !== selectedMetric) return undefined;
      if (previousData.granularity !== effectiveGranularity) return undefined;
      return previousData;
    },
    staleTime: 1000 * 60 * 2, // refresh template metadata reasonably often
  });

  const tileTemplateWithCacheBust = useMemo(() => {
    if (!tileTemplate?.tile_url) return tileTemplate;
    const bustedUrl = withCacheBust(tileTemplate.tile_url, tileCacheBustKey);
    if (bustedUrl === tileTemplate.tile_url) return tileTemplate;
    return {
      ...tileTemplate,
      tile_url: bustedUrl,
    };
  }, [tileTemplate, tileCacheBustKey]);

  // Double-buffer tile layers so switching dates doesn't briefly remove the overlay while tiles load.
  const [activeTileTemplate, setActiveTileTemplate] = useState<TileTemplateResponse | null>(null);
  const [pendingTileTemplate, setPendingTileTemplate] = useState<TileTemplateResponse | null>(null);
  const pendingTileTemplateRef = useRef<TileTemplateResponse | null>(null);
  const [activeTilesLoading, setActiveTilesLoading] = useState(false);

  useEffect(() => {
    pendingTileTemplateRef.current = pendingTileTemplate;
  }, [pendingTileTemplate]);

  useEffect(() => {
    if (!metricLayerMounted) {
      setActiveTileTemplate(null);
      setPendingTileTemplate(null);
      return;
    }

    if (!tileTemplateWithCacheBust?.tile_url) {
      setActiveTileTemplate(null);
      setPendingTileTemplate(null);
      return;
    }

    // If the overlay isn't currently visible, just track the latest template.
    // Double-buffering is only needed while the overlay is on-screen to prevent flicker.
    if (!metricLayerVisible) {
      if (!activeTileTemplate || activeTileTemplate.tile_url !== tileTemplateWithCacheBust.tile_url) {
        setActiveTileTemplate(tileTemplateWithCacheBust);
      }
      if (pendingTileTemplate) setPendingTileTemplate(null);
      return;
    }

    if (!activeTileTemplate) {
      setActiveTileTemplate(tileTemplateWithCacheBust);
      setPendingTileTemplate(null);
      return;
    }

    // Metric/granularity changes are semantic switches; don't keep showing the old overlay.
    if (
      activeTileTemplate.metric !== tileTemplateWithCacheBust.metric ||
      activeTileTemplate.granularity !== tileTemplateWithCacheBust.granularity
    ) {
      setActiveTileTemplate(tileTemplateWithCacheBust);
      setPendingTileTemplate(null);
      return;
    }

    if (activeTileTemplate.tile_url === tileTemplateWithCacheBust.tile_url) {
      setPendingTileTemplate(null);
      return;
    }

    if (pendingTileTemplate?.tile_url !== tileTemplateWithCacheBust.tile_url) {
      setPendingTileTemplate(tileTemplateWithCacheBust);
    }
  }, [
    activeTileTemplate,
    metricLayerMounted,
    metricLayerVisible,
    pendingTileTemplate,
    tileTemplateWithCacheBust,
  ]);

  const promotePendingLayer = useCallback((tileUrl: string) => {
    const pending = pendingTileTemplateRef.current;
    if (!pending || pending.tile_url !== tileUrl) return;
    setActiveTileTemplate(pending);
    setPendingTileTemplate(null);
  }, []);

  const activeOverlayEventHandlers = useMemo(
    () => ({
      loading: () => setActiveTilesLoading(true),
      load: () => setActiveTilesLoading(false),
      remove: () => setActiveTilesLoading(false),
    }),
    [setActiveTilesLoading]
  );

  const pendingOverlayEventHandlers = useMemo(() => {
    if (!pendingTileTemplate?.tile_url) return undefined;
    const tileUrl = pendingTileTemplate.tile_url;
    return {
      load: () => promotePendingLayer(tileUrl),
    };
  }, [pendingTileTemplate?.tile_url, promotePendingLayer]);

  useEffect(() => {
    if (!metricLayerMounted || !metricLayerVisible) {
      setActiveTilesLoading(false);
    }
  }, [metricLayerMounted, metricLayerVisible]);

  const overlayHasUnappliedTemplate = Boolean(
      metricLayerMounted &&
      metricLayerVisible &&
      activeTileTemplate?.tile_url &&
      tileTemplateWithCacheBust?.tile_url &&
      activeTileTemplate.metric === tileTemplateWithCacheBust.metric &&
      activeTileTemplate.granularity === tileTemplateWithCacheBust.granularity &&
      activeTileTemplate.tile_url !== tileTemplateWithCacheBust.tile_url
  );
  const overlayIsLoading = Boolean(
    overlayEnabled &&
      selectedMetric &&
      metricLayerMounted &&
      metricLayerVisible &&
      (
        tileTemplateIsLoading ||
        tileTemplateIsFetching ||
        Boolean(pendingTileTemplate) ||
        overlayHasUnappliedTemplate ||
        activeTilesLoading
      )
  );

  useEffect(() => {
    onOverlayLoadingChange?.(overlayIsLoading);
  }, [onOverlayLoadingChange, overlayIsLoading]);
  useEffect(() => {
    return () => onOverlayLoadingChange?.(false);
  }, [onOverlayLoadingChange]);

  const legendGradientStyle =
    selectedMetric !== 'cropland' && tileTemplateWithCacheBust?.palette?.length
      ? { background: `linear-gradient(to right, ${tileTemplateWithCacheBust.palette.join(', ')})` }
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
        ref={handleMapRef}
      >
        {useDarkBasemap ? (
          <TileLayer
            key="basemap:carto-dark"
            attribution={CARTO_DARK_ATTRIBUTION}
            url={CARTO_DARK_RASTER_URL}
            subdomains={['a', 'b', 'c', 'd']}
            updateWhenIdle={false}
            crossOrigin
          />
        ) : (
          <TileLayer
            key="basemap:maptiler-osm"
            attribution='<a href="https://www.maptiler.com/copyright/" target="_blank" rel="noreferrer">&copy; MapTiler</a> <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">&copy; OpenStreetMap contributors</a>'
            url={MAPTILER_OMT_RASTER_URL}
            tileSize={512}
            zoomOffset={-1}
            updateWhenIdle={false}
            crossOrigin
          />
        )}

        {/* Metric tile overlay (Earth Engine URL template) */}
        {metricLayerMounted && metricLayerVisible && activeTileTemplate?.tile_url && (
          <AbortableTileLayer
            key={activeTileTemplate.tile_url}
            url={activeTileTemplate.tile_url}
            opacity={activeTileTemplate.opacity}
            attribution={activeTileTemplate.attribution ?? undefined}
            updateWhenIdle={false}
            updateWhenZooming={false}
            keepBuffer={0}
            eventHandlers={activeOverlayEventHandlers}
          />
        )}
        {metricLayerMounted && metricLayerVisible && pendingTileTemplate?.tile_url && (
          <AbortableTileLayer
            key={pendingTileTemplate.tile_url}
            url={pendingTileTemplate.tile_url}
            opacity={0}
            // Avoid duplicate attributions while the pending layer is hidden.
            attribution={undefined}
            updateWhenIdle={false}
            updateWhenZooming={false}
            keepBuffer={0}
            eventHandlers={pendingOverlayEventHandlers}
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
        {overlayEnabled &&
          selectedMetric &&
          metricLayerMounted &&
          metricLayerVisible &&
          (tileTemplateIsLoading || tileTemplateIsFetching || Boolean(pendingTileTemplate)) && (
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
          !tileTemplateWithCacheBust?.tile_url && (
            <div className="map-overlay-hint">No overlay available for this metric/date.</div>
          )}
        {overlayEnabled && selectedMetric && (
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
