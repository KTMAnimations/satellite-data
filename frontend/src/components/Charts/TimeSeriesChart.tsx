import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import type { MetricData, MetricType } from '../../types';
import './Charts.css';

interface TimeSeriesChartProps {
  data: Record<MetricType, MetricData>;
  selectedMetrics: MetricType[];
  width?: number;
  height?: number;
}

const METRIC_COLORS: Record<MetricType, string> = {
  ndvi: '#059669',           // Emerald-600
  nightlights: '#D97706',    // Amber-600
  urban_density: '#7C3AED',  // Violet-600
  parking: '#0D9488',        // Teal-600
  land_cover: '#9333EA',     // Purple-600
  surface_water: '#2563EB',  // Blue-600
  active_fire: '#DC2626',    // Red-600
  no2: '#6366F1',            // Indigo-600
  temperature: '#EF4444',    // Red-500
  precipitation: '#3B82F6',  // Blue-500
  aerosol: '#92400E',        // Brown-600
  cropland: '#16A34A',       // Green-600
  evapotranspiration: '#0D9488', // Teal-600
  soil_moisture: '#7C3AED',  // Violet-600
  impervious: '#6B7280',     // Gray-500
  fire_historical: '#EA580C', // Orange-600
  canopy_height: '#15803D',  // Green-700
};

const METRIC_LABELS: Record<MetricType, string> = {
  ndvi: 'NDVI',
  nightlights: 'Nighttime Lights',
  urban_density: 'Urban Density',
  parking: 'Parking Occupancy',
  land_cover: 'Land Cover',
  surface_water: 'Surface Water',
  active_fire: 'Active Fire',
  no2: 'NO₂',
  temperature: 'Temperature',
  precipitation: 'Precipitation',
  aerosol: 'Aerosol',
  cropland: 'Cropland',
  evapotranspiration: 'Evapotranspiration',
  soil_moisture: 'Soil Moisture',
  impervious: 'Impervious Surface',
  fire_historical: 'Historical Fire',
  canopy_height: 'Canopy Height',
};

export function TimeSeriesChart({
  data,
  selectedMetrics,
  width = 600,
  height = 300,
}: TimeSeriesChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || selectedMetrics.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const margin = { top: 20, right: 80, bottom: 40, left: 50 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Combine all data points to determine scales
    const allDates: Date[] = [];
    const allValues: { metric: MetricType; value: number }[] = [];

    selectedMetrics.forEach((metric) => {
      const metricData = data[metric];
      if (metricData) {
        metricData.data.forEach((d) => {
          allDates.push(new Date(d.date));
          allValues.push({ metric, value: d.value });
        });
      }
    });

    if (allDates.length === 0) return;

    // X scale (time)
    const xScale = d3
      .scaleTime()
      .domain(d3.extent(allDates) as [Date, Date])
      .range([0, innerWidth]);

    // Create separate Y scales for each metric (normalized)
    const yScales: Record<MetricType, d3.ScaleLinear<number, number>> = {} as Record<
      MetricType,
      d3.ScaleLinear<number, number>
    >;

    selectedMetrics.forEach((metric) => {
      const metricData = data[metric];
      if (metricData) {
        const values = metricData.data.map((d) => d.value);
        yScales[metric] = d3
          .scaleLinear()
          .domain([Math.min(...values) * 0.9, Math.max(...values) * 1.1])
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
      const metricData = data[metric];
      if (!metricData || !yScales[metric]) return;

      const line = d3
        .line<{ date: string; value: number }>()
        .x((d) => xScale(new Date(d.date)))
        .y((d) => yScales[metric](d.value))
        .curve(d3.curveMonotoneX);

      // Line path
      g.append('path')
        .datum(metricData.data)
        .attr('fill', 'none')
        .attr('stroke', METRIC_COLORS[metric])
        .attr('stroke-width', 2)
        .attr('d', line);

      // Data points
      g.selectAll(`.dot-${metric}`)
        .data(metricData.data)
        .enter()
        .append('circle')
        .attr('class', `dot-${metric}`)
        .attr('cx', (d) => xScale(new Date(d.date)))
        .attr('cy', (d) => yScales[metric](d.value))
        .attr('r', 3)
        .attr('fill', METRIC_COLORS[metric])
        .style('cursor', 'pointer')
        .on('mouseover', function (event, d) {
          d3.select(this).attr('r', 5);
          // Show tooltip
          const tooltip = d3.select('.chart-tooltip');
          tooltip
            .style('opacity', 1)
            .style('left', `${event.pageX + 10}px`)
            .style('top', `${event.pageY - 10}px`)
            .html(`
              <strong>${METRIC_LABELS[metric]}</strong><br/>
              ${d.date}: ${d.value.toFixed(3)}
            `);
        })
        .on('mouseout', function () {
          d3.select(this).attr('r', 3);
          d3.select('.chart-tooltip').style('opacity', 0);
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
  }, [data, selectedMetrics, width, height]);

  return (
    <div className="chart-wrapper">
      <svg ref={svgRef} width={width} height={height} />
      <div className="chart-tooltip" />
    </div>
  );
}
