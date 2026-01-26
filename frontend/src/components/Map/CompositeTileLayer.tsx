import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';

interface CompositeTileLayerProps {
  baseUrl: string; // URL template with {z}/{x}/{y}
  nativeZoom: number; // The zoom level where tiles actually exist (11)
  minZoom?: number; // Minimum zoom to allow (default: 4)
  maxZoom?: number; // Maximum zoom to allow (default: 11)
  opacity?: number;
}

// Helper to load images with caching
function loadImage(
  url: string,
  cache: Map<string, HTMLImageElement>
): Promise<HTMLImageElement | null> {
  // Check cache first
  if (cache.has(url)) {
    return Promise.resolve(cache.get(url)!);
  }

  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      // Cache the image (limit cache size)
      if (cache.size > 500) {
        // Remove oldest entries
        const keysToDelete = Array.from(cache.keys()).slice(0, 100);
        keysToDelete.forEach((k) => cache.delete(k));
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
        // Below native zoom - need to composite multiple tiles
        const zoomDiff = nativeZoom - z;
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
    }) as L.GridLayer;

    layer.addTo(map);
    layerRef.current = layer;

    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
    };
  }, [map, baseUrl, nativeZoom, minZoom, maxZoom, opacity]);

  return null;
}
