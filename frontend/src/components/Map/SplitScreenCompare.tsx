import { useMemo, useState, useRef, useCallback, useEffect } from 'react';
import {
  MapContainer as LeafletMapContainer,
  TileLayer,
  GeoJSON,
  useMap,
} from 'react-leaflet';
import type { Granularity, Region, MetricType } from '../../types';
import { useTileTemplate } from '../../hooks/useTileTemplate';
import { METRIC_DEFAULT_GRANULARITY } from '../../config/metrics';
import { MAX_MAP_ZOOM, MIN_MAP_ZOOM } from '../../config/map';
import { AbortableTileLayer } from './AbortableTileLayer';
import './SplitScreenCompare.css';

function toDateBucket(dateStr: string, granularity: Granularity): string {
  return granularity === 'monthly' ? dateStr.slice(0, 7) : dateStr.slice(0, 10);
}


interface SplitScreenCompareProps {
  region: Region;
  metric: MetricType;
  dateA: string;
  dateB: string;
  labelA?: string;
  labelB?: string;
}

function SyncedMap({
  targetMap,
  onMove,
}: {
  targetMap: L.Map | null;
  onMove: () => void;
}) {
  const map = useMap();

  useEffect(() => {
    if (!targetMap) return;

    const syncMove = () => {
      const center = targetMap.getCenter();
      const zoom = targetMap.getZoom();
      if (map.getCenter().lat !== center.lat || map.getZoom() !== zoom) {
        map.setView(center, zoom, { animate: false });
      }
      onMove();
    };

    targetMap.on('move', syncMove);
    targetMap.on('zoom', syncMove);

    return () => {
      targetMap.off('move', syncMove);
      targetMap.off('zoom', syncMove);
    };
  }, [map, targetMap, onMove]);

  return null;
}

export function SplitScreenCompare({
  region,
  metric,
  dateA,
  dateB,
  labelA = 'Before',
  labelB = 'After',
}: SplitScreenCompareProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [splitPosition, setSplitPosition] = useState(50);
  const [isDragging, setIsDragging] = useState(false);
  const [mapA, setMapA] = useState<L.Map | null>(null);
  const [mapB, setMapB] = useState<L.Map | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const resizeRafRef = useRef<number | null>(null);
  const didInitialFitRef = useRef<string | null>(null);
  const fullscreenEnabled = typeof document !== 'undefined' && document.fullscreenEnabled;

  useEffect(() => {
    mapA?.attributionControl?.setPrefix(false);
    mapB?.attributionControl?.setPrefix(false);
  }, [mapA, mapB]);

  const { center, bounds } = useMemo(() => {
    const coords = region.geometry.coordinates[0];
    const lats = coords.map((c) => c[1]);
    const lngs = coords.map((c) => c[0]);

    const centerPoint: [number, number] = [
      (Math.min(...lats) + Math.max(...lats)) / 2,
      (Math.min(...lngs) + Math.max(...lngs)) / 2,
    ];

    const regionBounds: L.LatLngBoundsExpression = [
      [Math.min(...lats), Math.min(...lngs)],
      [Math.max(...lats), Math.max(...lngs)],
    ];

    return { center: centerPoint, bounds: regionBounds };
  }, [region.geometry.coordinates]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isDragging || !containerRef.current) return;

      const rect = containerRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const percentage = Math.max(10, Math.min(90, (x / rect.width) * 100));
      setSplitPosition(percentage);
    },
    [isDragging]
  );

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

  // Leaflet doesn't auto-detect container width changes. The split position
  // changes map container sizes, so we need to invalidate sizes to keep tiles
  // (and overlays) aligned while dragging.
  useEffect(() => {
    if (!mapA && !mapB) return;

    if (resizeRafRef.current) {
      cancelAnimationFrame(resizeRafRef.current);
    }

    resizeRafRef.current = requestAnimationFrame(() => {
      mapA?.invalidateSize({ pan: false, animate: false });
      mapB?.invalidateSize({ pan: false, animate: false });
      resizeRafRef.current = null;
    });

    return () => {
      if (resizeRafRef.current) {
        cancelAnimationFrame(resizeRafRef.current);
        resizeRafRef.current = null;
      }
    };
  }, [splitPosition, mapA, mapB]);

  const regionStyle = {
    color: '#06b6d4',
    weight: 2,
    fillColor: '#06b6d4',
    fillOpacity: 0,
  };

  const fitToRegion = useCallback(() => {
    const map = mapA ?? mapB;
    if (!map) return;
    map.fitBounds(bounds, {
      padding: [48, 48],
      maxZoom: Math.min(MAX_MAP_ZOOM, 13),
      animate: false,
    });
  }, [bounds, mapA, mapB]);

  useEffect(() => {
    if (!mapA || !mapB) return;
    if (didInitialFitRef.current === region.id) return;
    didInitialFitRef.current = region.id;
    fitToRegion();
  }, [fitToRegion, mapA, mapB, region.id]);

  const handleToggleFullscreen = useCallback(async () => {
    const target = containerRef.current;
    if (!target) return;

    try {
      if (document.fullscreenElement && document.fullscreenElement !== target) {
        await document.exitFullscreen();
      }

      if (document.fullscreenElement === target) {
        await document.exitFullscreen();
        return;
      }

      await target.requestFullscreen();
    } catch (err) {
      console.warn('Failed to toggle fullscreen:', err);
    }
  }, []);

  useEffect(() => {
    if (!fullscreenEnabled) return;

    const handleFullscreenChange = () => {
      const target = containerRef.current;
      const nowFullscreen = Boolean(target && document.fullscreenElement === target);
      setIsFullscreen(nowFullscreen);
      setMenuOpen(nowFullscreen);

      if (mapA || mapB) {
        requestAnimationFrame(() => {
          mapA?.invalidateSize({ pan: false, animate: false });
          mapB?.invalidateSize({ pan: false, animate: false });
        });
      }
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, [fullscreenEnabled, mapA, mapB]);

  const handleZoomIn = useCallback(() => {
    const map = mapA ?? mapB;
    if (!map) return;
    map.zoomIn(1, { animate: false });
  }, [mapA, mapB]);

  const handleZoomOut = useCallback(() => {
    const map = mapA ?? mapB;
    if (!map) return;
    map.zoomOut(1, { animate: false });
  }, [mapA, mapB]);

  const handleResetSplit = useCallback(() => {
    setSplitPosition(50);
  }, []);

  const handleMapMove = useCallback(() => {
    // Force re-render to sync maps
  }, []);

  const granularity = METRIC_DEFAULT_GRANULARITY[metric];
  const dateBucketA = toDateBucket(dateA, granularity);
  const dateBucketB = toDateBucket(dateB, granularity);

  const { data: tileTemplateA } = useTileTemplate(metric, dateBucketA, granularity);
  const { data: tileTemplateB } = useTileTemplate(metric, dateBucketB, granularity);

  return (
    <div
      ref={containerRef}
      className={`split-screen-compare ${isDragging ? 'dragging' : ''}`}
    >
      <div
        className="split-screen-menu"
        onMouseDown={(e) => e.stopPropagation()}
        onWheel={(e) => e.stopPropagation()}
      >
        <div className="split-screen-menu-row">
          <button
            type="button"
            className="btn btn-outline btn-icon split-screen-menu-toggle"
            onClick={() => setMenuOpen((v) => !v)}
            aria-label={menuOpen ? 'Close map menu' : 'Open map menu'}
            title={menuOpen ? 'Close menu' : 'Menu'}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 6h16" />
              <path d="M4 12h16" />
              <path d="M4 18h16" />
            </svg>
          </button>

          {fullscreenEnabled && (
            <button
              type="button"
              className="btn btn-outline btn-icon split-screen-fullscreen-btn"
              onClick={handleToggleFullscreen}
              aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
              title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
            >
              {isFullscreen ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 9h5V4" />
                  <path d="M21 9h-5V4" />
                  <path d="M3 15h5v5" />
                  <path d="M21 15h-5v5" />
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M8 3H3v5" />
                  <path d="M16 3h5v5" />
                  <path d="M8 21H3v-5" />
                  <path d="M16 21h5v-5" />
                </svg>
              )}
            </button>
          )}
        </div>

        {menuOpen && (
          <div className="split-screen-menu-panel">
            <button
              type="button"
              className="btn btn-outline split-screen-menu-item"
              onClick={handleZoomIn}
              aria-label="Zoom in"
              title="Zoom in"
            >
              <span className="split-screen-menu-item-icon" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 5v14" />
                  <path d="M5 12h14" />
                </svg>
              </span>
              Zoom in
            </button>

            <button
              type="button"
              className="btn btn-outline split-screen-menu-item"
              onClick={handleZoomOut}
              aria-label="Zoom out"
              title="Zoom out"
            >
              <span className="split-screen-menu-item-icon" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M5 12h14" />
                </svg>
              </span>
              Zoom out
            </button>

            <button
              type="button"
              className="btn btn-outline split-screen-menu-item"
              onClick={fitToRegion}
              aria-label="Reset view"
              title="Reset view"
            >
              <span className="split-screen-menu-item-icon" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a8 8 0 10-2.2 2.2" />
                  <path d="M22 22l-3.2-3.2" />
                </svg>
              </span>
              Reset view
            </button>

            <button
              type="button"
              className="btn btn-outline split-screen-menu-item"
              onClick={handleResetSplit}
              aria-label="Reset split position"
              title="Reset split"
            >
              <span className="split-screen-menu-item-icon" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 3v18" />
                  <path d="M5 7h6" />
                  <path d="M13 17h6" />
                </svg>
              </span>
              Reset split
            </button>
          </div>
        )}
      </div>

      {/* Map A (Before) */}
      <div className="split-map map-a" style={{ width: `${splitPosition}%` }}>
        <div className="map-label">
          <span className="label-text">{labelA}</span>
          <span className="label-date mono">{dateA}</span>
        </div>
        <LeafletMapContainer
          center={center}
          zoom={Math.min(MAX_MAP_ZOOM, MIN_MAP_ZOOM + 4)}
          minZoom={MIN_MAP_ZOOM}
          maxZoom={MAX_MAP_ZOOM}
          fadeAnimation={false}
          wheelDebounceTime={80}
          wheelPxPerZoomLevel={120}
          className="leaflet-map"
          ref={(m) => setMapA(m || null)}
          zoomControl={false}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          />
          {tileTemplateA?.tile_url && (
            <AbortableTileLayer
              key={`${metric}:${granularity}:${dateBucketA}`}
              url={tileTemplateA.tile_url}
              opacity={tileTemplateA.opacity}
              attribution={tileTemplateA.attribution ?? undefined}
              updateWhenIdle
              updateWhenZooming={false}
              keepBuffer={0}
            />
          )}
          <GeoJSON data={region.geometry as GeoJSON.Geometry} style={regionStyle} />
          {mapB && <SyncedMap targetMap={mapB} onMove={handleMapMove} />}
        </LeafletMapContainer>
      </div>

      {/* Divider */}
      <div
        className="split-divider"
        style={{ left: `${splitPosition}%` }}
        onMouseDown={handleMouseDown}
      >
        <div className="divider-line" />
        <div className="divider-handle">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M8 5v14l6-7-6-7z" />
            <path d="M16 5v14l-6-7 6-7z" transform="rotate(180 16 12)" />
          </svg>
        </div>
      </div>

      {/* Map B (After) */}
      <div
        className="split-map map-b"
        style={{ width: `${100 - splitPosition}%`, left: `${splitPosition}%` }}
      >
        <div className="map-label">
          <span className="label-text">{labelB}</span>
          <span className="label-date mono">{dateB}</span>
        </div>
        <LeafletMapContainer
          center={center}
          zoom={Math.min(MAX_MAP_ZOOM, MIN_MAP_ZOOM + 4)}
          minZoom={MIN_MAP_ZOOM}
          maxZoom={MAX_MAP_ZOOM}
          fadeAnimation={false}
          wheelDebounceTime={80}
          wheelPxPerZoomLevel={120}
          className="leaflet-map"
          ref={(m) => setMapB(m || null)}
          zoomControl={false}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          />
          {tileTemplateB?.tile_url && (
            <AbortableTileLayer
              key={`${metric}:${granularity}:${dateBucketB}`}
              url={tileTemplateB.tile_url}
              opacity={tileTemplateB.opacity}
              attribution={tileTemplateB.attribution ?? undefined}
              updateWhenIdle
              updateWhenZooming={false}
              keepBuffer={0}
            />
          )}
          <GeoJSON data={region.geometry as GeoJSON.Geometry} style={regionStyle} />
          {mapA && <SyncedMap targetMap={mapA} onMove={handleMapMove} />}
        </LeafletMapContainer>
      </div>
    </div>
  );
}
