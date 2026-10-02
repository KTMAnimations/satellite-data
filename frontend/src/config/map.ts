export const MIN_MAP_ZOOM = 4;
export const MAX_MAP_ZOOM = 16;

// Esri Canvas basemaps need no API key (CARTO's raster basemaps started requiring one).
const ESRI_CANVAS_BASE = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas';
export const BASEMAP_LIGHT_URL = `${ESRI_CANVAS_BASE}/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}`;
export const BASEMAP_DARK_URL = `${ESRI_CANVAS_BASE}/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}`;
export const BASEMAP_ATTRIBUTION =
  'Tiles &copy; <a href="https://www.esri.com/" target="_blank" rel="noreferrer">Esri</a> &mdash; ' +
  'Esri, HERE, Garmin, &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors';
