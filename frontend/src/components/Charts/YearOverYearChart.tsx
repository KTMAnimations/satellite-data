import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import type { MetricType } from '../../types';
import './Charts.css';

interface YearData {
  year: number;
  value: number;
}

interface YearOverYearChartProps {
  data: Record<MetricType, YearData[]>;
  selectedMetric: MetricType;
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

export function YearOverYearChart({
  data,
  selectedMetric,
  width = 500,
  height = 300,
}: YearOverYearChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  const metricData = data[selectedMetric];
  const hasData = metricData && metricData.length > 0;

  useEffect(() => {
    const svgElement = svgRef.current;
    if (!svgElement || !hasData) return;

    if (!metricData || metricData.length === 0) return;

    const svg = d3.select(svgElement);

    // Interrupt any ongoing transitions and clear previous content
    svg.selectAll('*').interrupt();
    svg.selectAll('*').remove();

    const margin = { top: 30, right: 30, bottom: 40, left: 60 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Sort by year
    const sortedData = [...metricData].sort((a, b) => a.year - b.year);

    // Scales
    const yScale = d3
      .scaleBand()
      .domain(sortedData.map((d) => String(d.year)))
      .range([0, innerHeight])
      .padding(0.3);

    const xMax = d3.max(sortedData, (d) => d.value) || 0;
    const xScale = d3.scaleLinear().domain([0, xMax * 1.1]).range([0, innerWidth]);

    // Grid lines
    g.append('g')
      .attr('class', 'grid')
      .call(
        d3
          .axisBottom(xScale)
          .tickSize(innerHeight)
          .tickFormat(() => '')
          .ticks(5)
      )
      .attr('stroke-opacity', 0.1);

    // Y axis (years)
    g.append('g')
      .attr('class', 'axis')
      .call(d3.axisLeft(yScale))
      .selectAll('text')
      .style('font-family', 'var(--font-mono)')
      .style('font-size', '12px')
      .style('fill', 'var(--text-secondary)');

    // X axis
    g.append('g')
      .attr('class', 'axis')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(xScale).ticks(5).tickFormat(d3.format('.2f')));

    // Check for reduced motion preference
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Bars - render immediately without staggered animations for better performance
    const bars = g.selectAll('.bar').data(sortedData);

    const barSelection = bars
      .enter()
      .append('rect')
      .attr('class', 'bar')
      .attr('y', (d) => yScale(String(d.year)) || 0)
      .attr('height', yScale.bandwidth())
      .attr('x', 0)
      .attr('fill', METRIC_COLORS[selectedMetric])
      .attr('rx', 4);

    // Apply animation only if not reduced motion, with shorter duration
    if (prefersReducedMotion) {
      barSelection.attr('width', (d) => xScale(d.value));
    } else {
      barSelection
        .attr('width', 0)
        .transition()
        .duration(300)
        .attr('width', (d) => xScale(d.value));
    }

    // Values at end of bars - no staggered animation
    g.selectAll('.bar-value')
      .data(sortedData)
      .enter()
      .append('text')
      .attr('class', 'bar-value')
      .attr('y', (d) => (yScale(String(d.year)) || 0) + yScale.bandwidth() / 2)
      .attr('x', (d) => xScale(d.value) + 8)
      .attr('dy', '0.35em')
      .attr('fill', 'var(--text-secondary)')
      .attr('font-family', 'var(--font-mono)')
      .attr('font-size', '11px')
      .text((d) => d.value.toFixed(3));

    // Year-over-year change indicators - no animation
    sortedData.forEach((d, i) => {
      if (i === 0) return;
      const prevValue = sortedData[i - 1].value;
      const change = ((d.value - prevValue) / prevValue) * 100;
      const isPositive = change > 0;

      const y = (yScale(String(d.year)) || 0) + yScale.bandwidth() / 2;

      g.append('text')
        .attr('x', innerWidth + 5)
        .attr('y', y)
        .attr('dy', '0.35em')
        .attr('fill', isPositive ? 'var(--metric-quaternary)' : 'var(--metric-alert)')
        .attr('font-family', 'var(--font-mono)')
        .attr('font-size', '10px')
        .text(`${isPositive ? '+' : ''}${change.toFixed(1)}%`);
    });

    // Title
    svg
      .append('text')
      .attr('x', width / 2)
      .attr('y', 18)
      .attr('text-anchor', 'middle')
      .attr('fill', 'var(--text-primary)')
      .attr('font-family', 'var(--font-body)')
      .attr('font-size', '14px')
      .attr('font-weight', '500')
      .text(`${METRIC_LABELS[selectedMetric]} - Year over Year`);

    // Cleanup function to prevent memory leaks
    return () => {
      svg.selectAll('*').interrupt();
      svg.selectAll('*').on('.', null); // Remove all event listeners
    };
  }, [data, selectedMetric, width, height, hasData, metricData]);

  // Show message when no data is available
  if (!hasData) {
    return (
      <div className="chart-wrapper yoy-chart" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height, color: '#78716C' }}>
        <div style={{ textAlign: 'center' }}>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ opacity: 0.5, marginBottom: '12px' }}>
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M3 9h18M9 21V9" />
          </svg>
          <p style={{ margin: 0, fontSize: '14px', fontWeight: 500 }}>No year-over-year data available</p>
          <p style={{ margin: '8px 0 0', fontSize: '12px', opacity: 0.7 }}>
            Select a date range spanning multiple years
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="chart-wrapper yoy-chart">
      <svg ref={svgRef} width={width} height={height} />
    </div>
  );
}
