import { useQuery } from '@tanstack/react-query';
import api from '../services/api';

export function useRegion(regionId: string | undefined) {
  return useQuery({
    queryKey: ['region', regionId],
    queryFn: ({ signal }) => api.getRegion(regionId!, { signal }),
    enabled: !!regionId,
  });
}
