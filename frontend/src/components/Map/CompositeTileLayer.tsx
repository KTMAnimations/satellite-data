import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';

export type CompositeTileEvent =
  | {
      kind: 'tile-start';
      coords: { z: number; x: number; y: number };
      composite: boolean;
      sourceTiles: number;
    }
  | {
      kind: 'tile-done';
      coords: { z: number; x: number; y: number };
      composite: boolean;
      sourceTiles: number;
      cacheHits: number;
      missingSources: number;
      durationMs: number;
    };

interface CompositeTileLayerProps {
  baseUrl: string; // URL template with {z}/{x}/{y}
  nativeZoom: number; // The zoom level where tiles actually exist (11)
  minZoom?: number; // Minimum zoom to allow (default: 4)
  maxZoom?: number; // Maximum zoom to allow (default: 11)
  opacity?: number;
  enabled?: boolean;
  /**
   * If false, the layer will render from the in-memory cache only and will not
   * issue any network requests for missing tiles.
   */
  allowNetwork?: boolean;
  onTileEvent?: (event: CompositeTileEvent) => void;
  /**
   * Prevents extremely expensive client-side compositing at very low zooms.
   * Example: nativeZoom=11 and z=4 would require 128×128=16,384 source tiles per displayed tile.
   */
  maxCompositeZoomDiff?: number; // Default: 2 (i.e., allow compositing down to z9 when nativeZoom=11)
}

// Maximum image cache size (LRU). This is purely in-memory and resets on page refresh.
// Large enough to make toggling between a couple dates feel instant, but still bounded.
const MAX_CACHE_SIZE = 400;

type LoadImageResult = { img: HTMLImageElement | null; cacheHit: boolean };

// Helper to load images with LRU-style caching
function loadImage(
  url: string,
  cache: Map<string, HTMLImageElement>,
  allowNetwork: boolean
): Promise<LoadImageResult> {
  // Check cache first - move to end to mark as recently used
  if (cache.has(url)) {
    const img = cache.get(url)!;
    cache.delete(url);
    cache.set(url, img);
    return Promise.resolve({ img, cacheHit: true });
  }

  if (!allowNetwork) {
    return Promise.resolve({ img: null, cacheHit: false });
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
      resolve({ img, cacheHit: false });
    };
    img.onerror = () => {
      resolve({ img: null, cacheHit: false });
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
  enabled = true,
  allowNetwork = true,
  onTileEvent,
  maxCompositeZoomDiff = 2,
}: CompositeTileLayerProps) {
  const map = useMap();
  const layerRef = useRef<L.GridLayer | null>(null);
  const tileCacheRef = useRef<Map<string, HTMLImageElement>>(new Map());

  // Single mutable ref for all prop values accessed inside the Leaflet
  // createTile callback and the redraw effect, avoiding 7+ separate refs.
  const propsRef = useRef({
    baseUrl,
    enabled,
    allowNetwork,
    nativeZoom,
    maxCompositeZoomDiff,
    onTileEvent,
    lastRenderedBaseUrl: null as string | null,
    lastEnabled: enabled,
    lastRenderedAllowNetwork: allowNetwork,
  });

  // Keep propsRef in sync on every render (no effects needed for these).
  propsRef.current.baseUrl = baseUrl;
  propsRef.current.enabled = enabled;
  propsRef.current.allowNetwork = allowNetwork;
  propsRef.current.nativeZoom = nativeZoom;
  propsRef.current.maxCompositeZoomDiff = maxCompositeZoomDiff;
  propsRef.current.onTileEvent = onTileEvent;

  // Create the Leaflet layer once; keep in-memory caches across baseUrl changes.
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

      if (!propsRef.current.enabled) {
        done(undefined, tile);
        return tile;
      }

      const z = coords.z;
      const x = coords.x;
      const y = coords.y;
      const now = performance.now();
      const allowNetworkNow = propsRef.current.allowNetwork;

      const effectiveNativeZoom = propsRef.current.nativeZoom;
      const isComposite = z < effectiveNativeZoom;
      const zoomDiff = isComposite ? effectiveNativeZoom - z : 0;
      const canComposite = isComposite && zoomDiff <= propsRef.current.maxCompositeZoomDiff;
      const sourceTiles = canComposite ? Math.pow(2, zoomDiff) ** 2 : isComposite ? 0 : 1;

      if (allowNetworkNow) {
        propsRef.current.onTileEvent?.({
          kind: 'tile-start',
          coords: { z, x, y },
          composite: isComposite,
          sourceTiles,
        });
      }

      if (z >= effectiveNativeZoom) {
        // At or above native zoom, just load the tile directly
        const url = propsRef.current.baseUrl
          .replace('{z}', String(effectiveNativeZoom))
          .replace('{x}', String(x))
          .replace('{y}', String(y));

        loadImage(url, tileCache, allowNetworkNow).then(({ img, cacheHit }) => {
          if (img) {
            ctx.drawImage(img, 0, 0, 256, 256);
          }

          if (allowNetworkNow) {
            propsRef.current.onTileEvent?.({
              kind: 'tile-done',
              coords: { z, x, y },
              composite: false,
              sourceTiles: 1,
              cacheHits: cacheHit ? 1 : 0,
              missingSources: img ? 0 : 1,
              durationMs: performance.now() - now,
            });
          }

          done(undefined, tile);
        });
      } else {
        const zoomDiff = effectiveNativeZoom - z;
        const effectiveMaxDiff = propsRef.current.maxCompositeZoomDiff;

        // Bail out if compositing would require too many source tiles.
        // This keeps the browser responsive when zoomed far out.
        if (zoomDiff > effectiveMaxDiff) {
          if (allowNetworkNow) {
            propsRef.current.onTileEvent?.({
              kind: 'tile-done',
              coords: { z, x, y },
              composite: true,
              sourceTiles: 0,
              cacheHits: 0,
              missingSources: 0,
              durationMs: performance.now() - now,
            });
          }
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
          cacheHit: boolean;
          dx: number;
          dy: number;
        }>[] = [];

        for (let ty = 0; ty < tilesPerSide; ty++) {
          for (let tx = 0; tx < tilesPerSide; tx++) {
            const tileX = nativeX + tx;
            const tileY = nativeY + ty;
            const url = propsRef.current.baseUrl
              .replace('{z}', String(effectiveNativeZoom))
              .replace('{x}', String(tileX))
              .replace('{y}', String(tileY));

            tilePromises.push(
              loadImage(url, tileCache, allowNetworkNow).then(({ img, cacheHit }) => ({
                img,
                cacheHit,
                dx: tx * tileSize,
                dy: ty * tileSize,
              }))
            );
          }
        }

        Promise.all(tilePromises).then((tiles) => {
          let cacheHits = 0;
          let missingSources = 0;

          // Draw all tiles onto the canvas
          for (const { img, cacheHit, dx, dy } of tiles) {
            if (cacheHit) cacheHits += 1;
            if (img) {
              ctx.drawImage(img, dx, dy, tileSize, tileSize);
            } else {
              missingSources += 1;
            }
          }

          if (allowNetworkNow) {
            propsRef.current.onTileEvent?.({
              kind: 'tile-done',
              coords: { z, x, y },
              composite: true,
              sourceTiles,
              cacheHits,
              missingSources,
              durationMs: performance.now() - now,
            });
          }

          done(undefined, tile);
        });
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
      // Keep initial opacity neutral; a separate effect keeps opacity in sync without recreating the layer.
      opacity: 0,
      tileSize: 256,
      // Performance: avoid extra tile work while panning/zooming and keep fewer offscreen tiles in memory.
      updateWhenIdle: true,
      updateWhenZooming: false,
      keepBuffer: 0,
    }) as L.GridLayer;

    layer.addTo(map);
    layerRef.current = layer;
    propsRef.current.lastRenderedBaseUrl = propsRef.current.baseUrl;
    propsRef.current.lastEnabled = propsRef.current.enabled;
    propsRef.current.lastRenderedAllowNetwork = propsRef.current.allowNetwork;

    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
      // Clear tile cache to free memory
      tileCache.clear();
    };
  }, [map, minZoom, maxZoom]);

  // Keep opacity in sync without recreating the layer.
  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) return;
    layer.setOpacity(enabled ? opacity : 0);
  }, [enabled, opacity]);

  // Redraw when enabling, when the base URL changes, or when network is re-enabled (manual fetch).
  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) return;

    const shouldEnable = propsRef.current.enabled;
    const baseUrlNow = propsRef.current.baseUrl;
    const baseUrlChanged = propsRef.current.lastRenderedBaseUrl !== baseUrlNow;
    const enabling = shouldEnable && !propsRef.current.lastEnabled;

    const allowNetworkNow = propsRef.current.allowNetwork;
    const allowNetworkBecameTrue = allowNetworkNow && !propsRef.current.lastRenderedAllowNetwork;

    // If we are disabled, don't redraw on baseUrl changes (keeps things quiet while scrubbing).
    if (!shouldEnable) {
      propsRef.current.lastEnabled = false;
      propsRef.current.lastRenderedAllowNetwork = allowNetworkNow;
      return;
    }

    if (enabling || baseUrlChanged || allowNetworkBecameTrue) {
      layer.redraw();
      propsRef.current.lastRenderedBaseUrl = baseUrlNow;
    }

    propsRef.current.lastEnabled = shouldEnable;
    propsRef.current.lastRenderedAllowNetwork = allowNetworkNow;
  }, [enabled, baseUrl, allowNetwork]);

  return null;
}
