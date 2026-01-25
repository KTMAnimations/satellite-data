import { useEffect, useRef, useMemo } from 'react';
import {
  MapContainer as LeafletMapContainer,
  TileLayer,
  GeoJSON,
  Rectangle,
  useMap,
  useMapEvents,
  FeatureGroup,
} from 'react-leaflet';
import { EditControl } from 'react-leaflet-draw';
import type { LatLngBounds, LatLngBoundsExpression, Map as LeafletMap } from 'leaflet';
import { useStore } from '../../store';
import type { Region, GeoJSONPolygon } from '../../types';
import api from '../../services/api';
import './MapContainer.css';

// Helper to compute bounds from GeoJSON coordinates
function getBoundsFromGeometry(geometry: GeoJSONPolygon | undefined): LatLngBoundsExpression | undefined {
  if (!geometry?.coordinates?.[0]) return undefined;

  const coords = geometry.coordinates[0];
  const lats = coords.map((c) => c[1]);
  const lngs = coords.map((c) => c[0]);

  return [
    [Math.min(...lats), Math.min(...lngs)],
    [Math.max(...lats), Math.max(...lngs)],
  ];
}

interface MapContainerProps {
  regions?: Region[];
  onRegionSelect?: (region: Region) => void;
  onRegionCreate?: (geometry: GeoJSONPolygon) => void;
  showDrawControls?: boolean;
  selectedMetric?: string;
  tileDate?: string;
  selectedRegion?: Region | null; // Optional prop to override store's selectedRegion
}

function MapController({
  selectedRegion,
}: {
  selectedRegion: Region | null;
}) {
  const map = useMap();

  useEffect(() => {
    if (selectedRegion) {
      // Use geometry if available, otherwise use bounds
      if (selectedRegion.geometry?.coordinates?.[0]) {
        const coords = selectedRegion.geometry.coordinates[0];
        const lats = coords.map((c) => c[1]);
        const lngs = coords.map((c) => c[0]);
        const bounds: LatLngBounds = [
          [Math.min(...lats), Math.min(...lngs)],
          [Math.max(...lats), Math.max(...lngs)],
        ] as unknown as LatLngBounds;
        map.fitBounds(bounds, { padding: [50, 50] });
      } else if (selectedRegion.bounds) {
        // Fallback to bounds property
        const { minLat, maxLat, minLon, maxLon } = selectedRegion.bounds;
        const bounds: LatLngBounds = [
          [minLat, minLon],
          [maxLat, maxLon],
        ] as unknown as LatLngBounds;
        map.fitBounds(bounds, { padding: [50, 50] });
      } else if (selectedRegion.center) {
        // Fallback to center
        map.setView([selectedRegion.center.lat, selectedRegion.center.lon], 10);
      }
    }
  }, [selectedRegion, map]);

  return null;
}

function MapEvents() {
  const { setMapCenter, setMapZoom } = useStore();

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
}: MapContainerProps) {
  const { mapState, selectedRegion: storeSelectedRegion } = useStore();
  const mapRef = useRef<LeafletMap | null>(null);

  // Use prop if provided, otherwise fall back to store
  const selectedRegion = selectedRegionProp !== undefined ? selectedRegionProp : storeSelectedRegion;

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
        className="map-container"
        ref={mapRef}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Metric overlay layer - constrained to region bounds */}
        {selectedRegion && selectedMetric && (() => {
          const regionBounds = getBoundsFromGeometry(selectedRegion.geometry);
          return regionBounds ? (
            <TileLayer
              key={`${selectedRegion.id}-${selectedMetric}-${tileDate}`}
              url={api.getTileUrl(selectedRegion.id, selectedMetric, tileDate)}
              opacity={0.7}
              bounds={regionBounds}
            />
          ) : null;
        })()}

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

        {/* Region rectangles - for demo/bounds-only regions */}
        {regions
          .filter((region) => !region.geometry?.coordinates && region.bounds)
          .map((region) => {
            const { minLat, maxLat, minLon, maxLon } = region.bounds;
            const style = getRegionStyle(region);
            return (
              <Rectangle
                key={region.id}
                bounds={[
                  [minLat, minLon],
                  [maxLat, maxLon],
                ]}
                pathOptions={style}
                eventHandlers={{
                  click: () => onRegionSelect?.(region),
                }}
              />
            );
          })}

        {/* Draw controls */}
        {showDrawControls && (
          <FeatureGroup>
            <EditControl
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
          </FeatureGroup>
        )}

        <MapController selectedRegion={selectedRegion} />
        <MapEvents />
      </LeafletMapContainer>

      {/* Map controls overlay */}
      <div className="map-controls">
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
