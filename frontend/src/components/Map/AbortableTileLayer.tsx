import { useEffect, useMemo, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';

type TileWithMeta = HTMLImageElement & {
  __satelliteAbortController?: AbortController;
  __satelliteObjectUrl?: string;
};

type AbortableTileLayerInstance = L.TileLayer & {
  __satelliteControllers?: Set<AbortController>;
};

type AbortableTileLayerConstructor = new (
  urlTemplate: string,
  options?: L.TileLayerOptions
) => AbortableTileLayerInstance;

type AbortableTileLayerProps = {
  url: string;
  opacity?: number;
  attribution?: string;
  zIndex?: number;
  tileSize?: number;
  keepBuffer?: number;
  updateWhenIdle?: boolean;
  updateWhenZooming?: boolean;
  crossOrigin?: boolean | L.CrossOrigin;
  eventHandlers?: L.LeafletEventHandlerFnMap;
};

const EMPTY_TILE_URL: string =
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (L as any).Util?.emptyImageUrl ?? 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=';

function createAbortableTileLayer(): AbortableTileLayerConstructor {
  return L.TileLayer.extend({
    createTile: function (coords: L.Coords, done: L.DoneCallback): HTMLElement {
      const tile = document.createElement('img') as TileWithMeta;
      tile.alt = '';
      tile.setAttribute('role', 'presentation');
      tile.decoding = 'async';
      tile.loading = 'lazy';
      tile.className = 'leaflet-tile';

      const options = this.options as L.TileLayerOptions;
      const crossOrigin = options.crossOrigin;
      if (crossOrigin === true) tile.crossOrigin = 'anonymous';
      if (typeof crossOrigin === 'string') tile.crossOrigin = crossOrigin;

      const controller = new AbortController();
      tile.__satelliteAbortController = controller;

      const layer = this as unknown as AbortableTileLayerInstance;
      const controllers = (layer.__satelliteControllers ??= new Set());
      controllers.add(controller);

      let finished = false;
      const finish = (err?: unknown) => {
        if (finished) return;
        finished = true;
        controllers.delete(controller);
        tile.__satelliteAbortController = undefined;
        const error = err instanceof Error ? err : err ? new Error(String(err)) : undefined;
        done(error, tile);
      };

      const url = (this as unknown as L.TileLayer).getTileUrl(coords);

      fetch(url, { signal: controller.signal })
        .then((res) => {
          if (!res.ok) throw new Error(`Tile fetch failed (${res.status})`);
          return res.blob();
        })
        .then((blob) => {
          if (controller.signal.aborted) {
            tile.src = EMPTY_TILE_URL;
            finish();
            return;
          }
          const objectUrl = URL.createObjectURL(blob);
          tile.__satelliteObjectUrl = objectUrl;
          tile.src = objectUrl;
        })
        .catch((err) => {
          tile.src = EMPTY_TILE_URL;
          if (controller.signal.aborted) {
            finish();
            return;
          }
          finish(err);
        });

      tile.onload = () => finish();
      tile.onerror = () => {
        tile.src = EMPTY_TILE_URL;
        finish(new Error('Tile image failed to load'));
      };

      return tile;
    },
  }) as unknown as AbortableTileLayerConstructor;
}

export function AbortableTileLayer({
  url,
  opacity = 1,
  attribution,
  zIndex,
  tileSize,
  keepBuffer,
  updateWhenIdle,
  updateWhenZooming,
  crossOrigin,
  eventHandlers,
}: AbortableTileLayerProps) {
  const map = useMap();
  const layerRef = useRef<AbortableTileLayerInstance | null>(null);
  const eventHandlersRef = useRef<L.LeafletEventHandlerFnMap | undefined>(undefined);

  const LayerClass = useMemo(() => createAbortableTileLayer(), []);

  useEffect(() => {
    const options: L.TileLayerOptions = { opacity };
    if (attribution) options.attribution = attribution;
    if (typeof zIndex === 'number') options.zIndex = zIndex;
    if (typeof tileSize === 'number') options.tileSize = tileSize;
    if (typeof keepBuffer === 'number') options.keepBuffer = keepBuffer;
    if (typeof updateWhenIdle === 'boolean') options.updateWhenIdle = updateWhenIdle;
    if (typeof updateWhenZooming === 'boolean') options.updateWhenZooming = updateWhenZooming;
    if (crossOrigin !== undefined) options.crossOrigin = crossOrigin;

    const layer = new LayerClass(url, options);
    layerRef.current = layer;

    const handleTileUnload = (e: { tile: HTMLElement }) => {
      const tile = e.tile as TileWithMeta;
      tile.__satelliteAbortController?.abort();
      tile.__satelliteAbortController = undefined;

      if (tile.__satelliteObjectUrl) {
        URL.revokeObjectURL(tile.__satelliteObjectUrl);
        tile.__satelliteObjectUrl = undefined;
      }
      tile.src = EMPTY_TILE_URL;
    };

    const handleRemove = () => {
      const controllers = layer.__satelliteControllers;
      controllers?.forEach((c) => c.abort());
      controllers?.clear();
    };

    layer.on('tileunload', handleTileUnload);
    layer.on('remove', handleRemove);

    if (eventHandlers) {
      layer.on(eventHandlers);
      eventHandlersRef.current = eventHandlers;
    }

    // React StrictMode re-runs effects on mount in development; defer adding the layer
    // so the "test" mount can be cleaned up before we start issuing tile requests.
    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (cancelled) return;
      layer.addTo(map);
    }, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      // Remove the layer *before* detaching handlers so in-flight tile fetches
      // get aborted immediately during metric/date swaps.
      if (map.hasLayer(layer)) {
        map.removeLayer(layer);
      } else {
        // If the layer was never added (e.g. StrictMode test mount), still ensure
        // any tracked controllers are aborted.
        handleRemove();
      }

      layer.off('tileunload', handleTileUnload);
      layer.off('remove', handleRemove);
      layerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [LayerClass, map, url]);

  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) return;

    if (eventHandlersRef.current === eventHandlers) {
      return () => {
        if (eventHandlers) layer.off(eventHandlers);
      };
    }

    if (eventHandlersRef.current) layer.off(eventHandlersRef.current);
    if (eventHandlers) layer.on(eventHandlers);
    eventHandlersRef.current = eventHandlers;

    return () => {
      if (eventHandlers) layer.off(eventHandlers);
    };
  }, [eventHandlers]);

  // Keep mutable options in sync without recreating the layer.
  useEffect(() => {
    layerRef.current?.setOpacity(opacity);
  }, [opacity]);

  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) return;
    if (typeof zIndex === 'number') layer.setZIndex(zIndex);
  }, [zIndex]);

  return null;
}
