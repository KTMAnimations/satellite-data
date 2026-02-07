import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import type { Granularity, MetricType } from '../types';

export function useTileTemplate(
  metric: MetricType | undefined,
  dateBucket: string | undefined,
  granularity: Granularity | undefined,
) {
  return useQuery({
    queryKey: ['tiles', 'template', metric, dateBucket, granularity],
    queryFn: ({ signal }) =>
      api.getTileTemplate(
        { metric: metric!, date_bucket: dateBucket!, granularity: granularity! },
        { signal },
      ),
    enabled: Boolean(metric && dateBucket && granularity),
    staleTime: 1000 * 60 * 60,
  });
}
