import { memo, useEffect, useRef } from 'react';
import * as d3 from 'd3';
import type { MetricData, MetricType } from '../../types';
import { parseMetricDate } from '../../utils/dates';
import { METRIC_COLORS, METRIC_LABELS } from '../../config/metrics';
import { ensureGlobalChartTooltip, hideGlobalChartTooltip, showGlobalChartTooltip } from './chartTooltip';
import './Charts.css';

interface TimeSeriesChartProps {
  data: Partial<Record<MetricType, MetricData>>;
  selectedMetrics: MetricType[];
  width?: number;
  height?: number;
}

function formatChartValue(value: number): string {
  const abs = Math.abs(value);
  const digits = abs < 1 ? 4 : 3;
  return value.toFixed(digits);
}

export const TimeSeriesChart = memo(function TimeSeriesChart({
  data,
  selectedMetrics,
  width = 600,
  height = 300,
}: TimeSeriesChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  // Check if there's actual data to display
  const hasData = selectedMetrics.some((metric) => {
    const metricData = data[metric];
    return metricData && metricData.data && metricData.data.length > 0;
  });

  useEffect(() => {
    const svgElement = svgRef.current;
    if (!svgElement || selectedMetrics.length === 0 || !hasData) return;

    ensureGlobalChartTooltip();

    const svg = d3.select(svgElement);

    // Interrupt any ongoing transitions and clear previous content
    svg.selectAll('*').interrupt();
    svg.selectAll('*').remove();

    const margin = { top: 20, right: 80, bottom: 40, left: 50 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Combine all data points to determine scales
    const allDates: Date[] = [];
    const parsedDataByMetric: Partial<Record<MetricType, Array<{ date: Date; value: number; rawDate: string }>>> = {};

    selectedMetrics.forEach((metric) => {
      const metricData = data[metric];
      if (metricData) {
        const parsed = metricData.data.flatMap((d) => {
          const parsedDate = parseMetricDate(d.date);
          if (!parsedDate) return [];
          return [{ date: parsedDate, value: d.value, rawDate: d.date }];
        });
        if (parsed.length > 0) {
          parsedDataByMetric[metric] = parsed;
          parsed.forEach((p) => allDates.push(p.date));
        }
      }
    });

    if (allDates.length === 0) return;

    // X scale (time)
    const xScale = d3
      .scaleTime()
      .domain(d3.extent(allDates) as [Date, Date])
      .range([0, innerWidth]);

    // Create separate Y scales for each metric (normalized)
    const yScales: Partial<Record<MetricType, d3.ScaleLinear<number, number>>> = {};

    selectedMetrics.forEach((metric) => {
      const metricData = parsedDataByMetric[metric];
      if (metricData) {
        const values = metricData.map((d) => d.value);
        const minValue = Math.min(...values);
        const maxValue = Math.max(...values);
        const range = maxValue - minValue;
        const padding = range > 0 ? range * 0.1 : (Math.abs(minValue) || 1) * 0.1;
        yScales[metric] = d3
          .scaleLinear()
          .domain([minValue - padding, maxValue + padding])
          .range([innerHeight, 0]);
      }
    });

    // X axis
    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(xScale).ticks(6))
      .attr('class', 'axis');

    // Draw lines for each metric
    selectedMetrics.forEach((metric) => {
      const metricData = parsedDataByMetric[metric];
      const yScale = yScales[metric];
      if (!metricData || !yScale) return;

      const line = d3
        .line<{ date: Date; value: number }>()
        .x((d) => xScale(d.date))
        .y((d) => yScale(d.value))
        .curve(d3.curveMonotoneX);

      // Line path
      g.append('path')
        .datum(metricData)
        .attr('fill', 'none')
        .attr('stroke', METRIC_COLORS[metric])
        .attr('stroke-width', 2)
        .attr('d', line);

      // Data points
      g.selectAll(`.dot-${metric}`)
        .data(metricData)
        .enter()
        .append('circle')
        .attr('class', `dot-${metric}`)
        .attr('cx', (d) => xScale(d.date))
        .attr('cy', (d) => yScale(d.value))
        .attr('r', 3)
        .attr('fill', METRIC_COLORS[metric])
        .style('cursor', 'pointer')
        .on('mouseover', function (event, d) {
          d3.select(this).attr('r', 5);
          showGlobalChartTooltip(
            event,
            `
              <strong>${METRIC_LABELS[metric]}</strong><br/>
              ${d.rawDate}: ${formatChartValue(d.value)}
            `,
            { offsetX: 10, offsetY: -10 }
          );
        })
        .on('mouseout', function () {
          d3.select(this).attr('r', 3);
          hideGlobalChartTooltip();
        });
    });

    // Legend
    const legend = g
      .append('g')
      .attr('transform', `translate(${innerWidth + 10}, 0)`);

    selectedMetrics.forEach((metric, i) => {
      const legendRow = legend.append('g').attr('transform', `translate(0, ${i * 20})`);

      legendRow
        .append('rect')
        .attr('width', 12)
        .attr('height', 12)
        .attr('fill', METRIC_COLORS[metric]);

      legendRow
        .append('text')
        .attr('x', 18)
        .attr('y', 10)
        .attr('font-size', '11px')
        .text(METRIC_LABELS[metric]);
    });
    // Cleanup function to prevent memory leaks
    return () => {
      svg.selectAll('*').interrupt();
      svg.selectAll('*').on('.', null); // Remove all event listeners
    };
  }, [data, selectedMetrics, width, height, hasData]);

  // Show message when no data is available
  if (!hasData) {
    return (
      <div className="chart-wrapper" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height, color: '#78716C' }}>
        <div style={{ textAlign: 'center' }}>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ opacity: 0.5, marginBottom: '12px' }}>
            <path d="M3 3v18h18" />
            <path d="M7 16l4-4 4 4 5-6" opacity="0.3" />
          </svg>
          <p style={{ margin: 0, fontSize: '14px', fontWeight: 500 }}>No observations available</p>
          <p style={{ margin: '8px 0 0', fontSize: '12px', opacity: 0.7 }}>
            Try adjusting the date range or selecting different metrics
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="chart-wrapper">
      <svg ref={svgRef} width={width} height={height} />
    </div>
  );
});
