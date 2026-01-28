import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';

interface CompositeTileLayerProps {
  baseUrl: string; // URL template with {z}/{x}/{y}
  nativeZoom: number; // The zoom level where tiles actually exist (11)
  minZoom?: number; // Minimum zoom to allow (default: 4)
  maxZoom?: number; // Maximum zoom to allow (default: 11)
  opacity?: number;
  /**
   * Prevents extremely expensive client-side compositing at very low zooms.
   * Example: nativeZoom=11 and z=4 would require 128×128=16,384 source tiles per displayed tile.
   */
  maxCompositeZoomDiff?: number; // Default: 2 (i.e., allow compositing down to z9 when nativeZoom=11)
}

// Maximum cache size - keep small to avoid memory issues
// Reduced from 100 to 50 for better memory usage
const MAX_CACHE_SIZE = 50;

// Helper to load images with LRU-style caching
function loadImage(
  url: string,
  cache: Map<string, HTMLImageElement>
): Promise<HTMLImageElement | null> {
  // Check cache first - move to end to mark as recently used
  if (cache.has(url)) {
    const img = cache.get(url)!;
    cache.delete(url);
    cache.set(url, img);
    return Promise.resolve(img);
  }

  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      // Evict oldest entries if at capacity (LRU eviction)
      while (cache.size >= MAX_CACHE_SIZE) {
        const oldestKey = cache.keys().next().value;
        if (oldestKey) cache.delete(oldestKey);
      }
      cache.set(url, img);
      resolve(img);
    };
    img.onerror = () => {
      resolve(null);
    };
    img.src = url;
  });
}

/**
 * A custom tile layer that composites higher-zoom tiles when viewing at lower zoom levels.
 *
 * When the map is at zoom < nativeZoom, this layer:
 * 1. Calculates which native-zoom tiles cover the requested area
 * 2. Fetches those tiles
 * 3. Composites them into a single tile using canvas
 *
 * This allows viewing z11 data at z4-z10 with progressively lower resolution.
 */
export function CompositeTileLayer({
  baseUrl,
  nativeZoom = 11,
  minZoom = 4,
  maxZoom = 11,
  opacity = 0.7,
  maxCompositeZoomDiff = 2,
}: CompositeTileLayerProps) {
  const map = useMap();
  const layerRef = useRef<L.GridLayer | null>(null);
  const tileCacheRef = useRef<Map<string, HTMLImageElement>>(new Map());

  useEffect(() => {
    const tileCache = tileCacheRef.current;

    // Create tile function
    const createTile = function (
      this: L.GridLayer,
      coords: L.Coords,
      done: L.DoneCallback
    ): HTMLElement {
      const tile = document.createElement('canvas') as HTMLCanvasElement;
      tile.width = 256;
      tile.height = 256;
      const ctx = tile.getContext('2d')!;

      const z = coords.z;
      const x = coords.x;
      const y = coords.y;

      if (z >= nativeZoom) {
        // At or above native zoom, just load the tile directly
        const url = baseUrl
          .replace('{z}', String(nativeZoom))
          .replace('{x}', String(x))
          .replace('{y}', String(y));

        loadImage(url, tileCache)
          .then((img) => {
            if (img) {
              ctx.drawImage(img, 0, 0, 256, 256);
            }
            done(undefined, tile);
          })
          .catch(() => done(undefined, tile));
      } else {
        const zoomDiff = nativeZoom - z;

        // Bail out if compositing would require too many source tiles.
        // This keeps the browser responsive when zoomed far out.
        if (zoomDiff > maxCompositeZoomDiff) {
          done(undefined, tile);
          return tile;
        }

        // Below native zoom - need to composite multiple tiles
        const scale = Math.pow(2, zoomDiff);
        const tilesPerSide = scale;

        // Calculate the range of native tiles needed
        const nativeX = x * scale;
        const nativeY = y * scale;

        // Size of each source tile when drawn on our 256x256 canvas
        const tileSize = 256 / tilesPerSide;

        // Load all required tiles
        const tilePromises: Promise<{
          img: HTMLImageElement | null;
          dx: number;
          dy: number;
        }>[] = [];

        for (let ty = 0; ty < tilesPerSide; ty++) {
          for (let tx = 0; tx < tilesPerSide; tx++) {
            const tileX = nativeX + tx;
            const tileY = nativeY + ty;
            const url = baseUrl
              .replace('{z}', String(nativeZoom))
              .replace('{x}', String(tileX))
              .replace('{y}', String(tileY));

            tilePromises.push(
              loadImage(url, tileCache).then((img) => ({
                img,
                dx: tx * tileSize,
                dy: ty * tileSize,
              }))
            );
          }
        }

        Promise.all(tilePromises)
          .then((tiles) => {
            // Draw all tiles onto the canvas
            for (const { img, dx, dy } of tiles) {
              if (img) {
                ctx.drawImage(img, dx, dy, tileSize, tileSize);
              }
            }
            done(undefined, tile);
          })
          .catch(() => done(undefined, tile));
      }

      return tile;
    };

    // Create the layer using GridLayer.extend pattern
    const CompositeLayerClass = L.GridLayer.extend({
      createTile: createTile,
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const layer = new (CompositeLayerClass as any)({
      minZoom,
      maxZoom,
      opacity,
      tileSize: 256,
      // Performance: avoid extra tile work while panning/zooming and keep fewer offscreen tiles in memory.
      updateWhenIdle: true,
      keepBuffer: 1,
    }) as L.GridLayer;

    layer.addTo(map);
    layerRef.current = layer;

    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
      // Clear tile cache to free memory
      tileCache.clear();
    };
  }, [map, baseUrl, nativeZoom, minZoom, maxZoom, opacity, maxCompositeZoomDiff]);

  return null;
}
