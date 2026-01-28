import { useState, useRef, useCallback, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  MapContainer as LeafletMapContainer,
  TileLayer,
  GeoJSON,
  useMap,
} from 'react-leaflet';
import type { Granularity, Region, MetricType } from '../../types';
import api from '../../services/api';
import { METRIC_DEFAULT_GRANULARITY } from '../../config/metrics';
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
  const resizeRafRef = useRef<number | null>(null);

  // Calculate center from region geometry
  const coords = region.geometry.coordinates[0];
  const lats = coords.map((c) => c[1]);
  const lngs = coords.map((c) => c[0]);
  const center: [number, number] = [
    (Math.min(...lats) + Math.max(...lats)) / 2,
    (Math.min(...lngs) + Math.max(...lngs)) / 2,
  ];

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
    fillOpacity: 0.1,
  };

  const handleMapMove = useCallback(() => {
    // Force re-render to sync maps
  }, []);

  const granularity = METRIC_DEFAULT_GRANULARITY[metric];
  const dateBucketA = toDateBucket(dateA, granularity);
  const dateBucketB = toDateBucket(dateB, granularity);

  const { data: tileTemplateA } = useQuery({
    queryKey: ['tiles', 'template', metric, dateBucketA, granularity],
    queryFn: () =>
      api.getTileTemplate({
        metric,
        date_bucket: dateBucketA,
        granularity,
      }),
    enabled: Boolean(metric && dateBucketA && granularity),
    staleTime: 1000 * 60 * 60,
  });

  const { data: tileTemplateB } = useQuery({
    queryKey: ['tiles', 'template', metric, dateBucketB, granularity],
    queryFn: () =>
      api.getTileTemplate({
        metric,
        date_bucket: dateBucketB,
        granularity,
      }),
    enabled: Boolean(metric && dateBucketB && granularity),
    staleTime: 1000 * 60 * 60,
  });

  return (
    <div
      ref={containerRef}
      className={`split-screen-compare ${isDragging ? 'dragging' : ''}`}
    >
      {/* Map A (Before) */}
      <div className="split-map map-a" style={{ width: `${splitPosition}%` }}>
        <div className="map-label">
          <span className="label-text">{labelA}</span>
          <span className="label-date mono">{dateA}</span>
        </div>
        <LeafletMapContainer
          center={center}
          zoom={10}
          minZoom={9}
          maxZoom={11}
          className="leaflet-map"
          ref={(m) => setMapA(m || null)}
          zoomControl={false}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          />
          {tileTemplateA?.tile_url && (
            <TileLayer
              key={`${metric}:${granularity}:${dateBucketA}`}
              url={tileTemplateA.tile_url}
              opacity={tileTemplateA.opacity}
              attribution={tileTemplateA.attribution ?? undefined}
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
          zoom={10}
          minZoom={9}
          maxZoom={11}
          className="leaflet-map"
          ref={(m) => setMapB(m || null)}
          zoomControl={false}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          />
          {tileTemplateB?.tile_url && (
            <TileLayer
              key={`${metric}:${granularity}:${dateBucketB}`}
              url={tileTemplateB.tile_url}
              opacity={tileTemplateB.opacity}
              attribution={tileTemplateB.attribution ?? undefined}
            />
          )}
          <GeoJSON data={region.geometry as GeoJSON.Geometry} style={regionStyle} />
          {mapA && <SyncedMap targetMap={mapA} onMove={handleMapMove} />}
        </LeafletMapContainer>
      </div>

      {/* Legend */}
      <div className="comparison-legend">
        <div className="legend-item decrease">
          <span className="color-swatch" />
          <span>Decrease</span>
        </div>
        <div className="legend-item increase">
          <span className="color-swatch" />
          <span>Increase</span>
        </div>
      </div>
    </div>
  );
}
