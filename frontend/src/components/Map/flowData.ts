import type { FlowPoint } from './FlowLayer';

// Helper function to create flow data from region metrics
export function createFlowData(
  regions: Array<{ id: string; name: string; lat: number; lng: number }>,
  winterValues: Record<string, number>,
  summerValues: Record<string, number>
): FlowPoint[] {
  return regions.map((region) => {
    const winter = winterValues[region.id] || 0;
    const summer = summerValues[region.id] || 0;
    const total = winter + summer || 1;

    // Normalize: 0 = all summer activity, 1 = all winter activity
    const value = winter / total;

    return {
      id: region.id,
      name: region.name,
      lat: region.lat,
      lng: region.lng,
      value,
    };
  });
}

