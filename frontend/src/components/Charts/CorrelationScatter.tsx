import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import type { MetricType } from '../../types';
import './Charts.css';
import { ensureGlobalChartTooltip, hideGlobalChartTooltip, showGlobalChartTooltip } from './chartTooltip';

interface DataPoint {
  x: number;
  y: number;
  label?: string;
  date?: string;
}

interface CorrelationScatterProps {
  data: DataPoint[];
  xMetric: MetricType;
  yMetric: MetricType;
  width?: number;
  height?: number;
  showTrendline?: boolean;
}

const METRIC_LABELS: Record<MetricType, string> = {
  ndvi: 'NDVI',
  nightlights: 'Nighttime Lights',
  urban_density: 'Urban Density',
  parking: 'Parking Occupancy',
  land_cover: 'Land Cover',
  surface_water: 'Surface Water',
  no2: 'NO₂',
  temperature: 'Temperature',
  precipitation: 'Precipitation',
  aerosol: 'Aerosol',
  cropland: 'Cropland',
  evapotranspiration: 'Evapotranspiration',
  soil_moisture: 'Soil Moisture',
  impervious: 'Impervious Surface',
  canopy_height: 'Canopy Height',
};

const METRIC_COLORS: Record<MetricType, string> = {
  ndvi: '#059669',           // Emerald-600
  nightlights: '#D97706',    // Amber-600
  urban_density: '#7C3AED',  // Violet-600
  parking: '#0D9488',        // Teal-600
  land_cover: '#9333EA',     // Purple-600
  surface_water: '#2563EB',  // Blue-600
  no2: '#6366F1',            // Indigo-600
  temperature: '#EF4444',    // Red-500
  precipitation: '#3B82F6',  // Blue-500
  aerosol: '#92400E',        // Brown-600
  cropland: '#16A34A',       // Green-600
  evapotranspiration: '#0D9488', // Teal-600
  soil_moisture: '#7C3AED',  // Violet-600
  impervious: '#6B7280',     // Gray-500
  canopy_height: '#15803D',  // Green-700
};

// Calculate linear regression
function linearRegression(data: DataPoint[]): { slope: number; intercept: number; r2: number } {
  const n = data.length;
  if (n < 2) return { slope: 0, intercept: 0, r2: 0 };

  const sumX = d3.sum(data, (d) => d.x);
  const sumY = d3.sum(data, (d) => d.y);
  const sumXY = d3.sum(data, (d) => d.x * d.y);
  const sumX2 = d3.sum(data, (d) => d.x * d.x);

  const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
  const intercept = (sumY - slope * sumX) / n;

  // R-squared
  const yMean = sumY / n;
  const ssRes = d3.sum(data, (d) => Math.pow(d.y - (slope * d.x + intercept), 2));
  const ssTot = d3.sum(data, (d) => Math.pow(d.y - yMean, 2));
  const r2 = ssTot === 0 ? 0 : 1 - ssRes / ssTot;

  return { slope, intercept, r2 };
}

export function CorrelationScatter({
  data,
  xMetric,
  yMetric,
  width = 400,
  height = 400,
  showTrendline = true,
}: CorrelationScatterProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const hasData = data && data.length > 0;

  useEffect(() => {
    const svgElement = svgRef.current;
    if (!svgElement || !hasData) return;

    ensureGlobalChartTooltip();

    const svg = d3.select(svgElement);

    // Interrupt any ongoing transitions and clear previous content
    svg.selectAll('*').interrupt();
    svg.selectAll('*').remove();

    const margin = { top: 40, right: 30, bottom: 60, left: 60 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Scales
    const xExtent = d3.extent(data, (d) => d.x) as [number, number];
    const yExtent = d3.extent(data, (d) => d.y) as [number, number];

    const xPadding = (xExtent[1] - xExtent[0]) * 0.1;
    const yPadding = (yExtent[1] - yExtent[0]) * 0.1;

    const xScale = d3
      .scaleLinear()
      .domain([xExtent[0] - xPadding, xExtent[1] + xPadding])
      .range([0, innerWidth]);

    const yScale = d3
      .scaleLinear()
      .domain([yExtent[0] - yPadding, yExtent[1] + yPadding])
      .range([innerHeight, 0]);

    // Grid
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

    g.append('g')
      .attr('class', 'grid')
      .call(
        d3
          .axisLeft(yScale)
          .tickSize(-innerWidth)
          .tickFormat(() => '')
          .ticks(5)
      )
      .attr('stroke-opacity', 0.1);

    // Axes
    g.append('g')
      .attr('class', 'axis')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(xScale).ticks(5).tickFormat(d3.format('.2f')));

    g.append('g').attr('class', 'axis').call(d3.axisLeft(yScale).ticks(5).tickFormat(d3.format('.2f')));

    // Axis labels
    g.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', innerHeight + 45)
      .attr('text-anchor', 'middle')
      .attr('fill', 'var(--text-secondary)')
      .attr('font-family', 'var(--font-body)')
      .attr('font-size', '12px')
      .text(METRIC_LABELS[xMetric]);

    g.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -innerHeight / 2)
      .attr('y', -45)
      .attr('text-anchor', 'middle')
      .attr('fill', 'var(--text-secondary)')
      .attr('font-family', 'var(--font-body)')
      .attr('font-size', '12px')
      .text(METRIC_LABELS[yMetric]);

    // Trendline
    if (showTrendline && data.length >= 2) {
      const { slope, intercept, r2 } = linearRegression(data);

      const x1 = xExtent[0] - xPadding;
      const x2 = xExtent[1] + xPadding;
      const y1 = slope * x1 + intercept;
      const y2 = slope * x2 + intercept;

      g.append('line')
        .attr('class', 'trendline')
        .attr('x1', xScale(x1))
        .attr('y1', yScale(y1))
        .attr('x2', xScale(x2))
        .attr('y2', yScale(y2))
        .attr('stroke', 'var(--accent-primary)')
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', '6,4')
        .attr('opacity', 0.7);

      // R² value
      g.append('text')
        .attr('x', innerWidth - 10)
        .attr('y', 20)
        .attr('text-anchor', 'end')
        .attr('fill', 'var(--accent-primary)')
        .attr('font-family', 'var(--font-mono)')
        .attr('font-size', '12px')
        .text(`R² = ${r2.toFixed(3)}`);
    }

    // Check for reduced motion preference
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Data points - limit staggered animation to avoid performance issues
    const points = g.selectAll('.point').data(data);

    const pointSelection = points
      .enter()
      .append('circle')
      .attr('class', 'point')
      .attr('cx', (d) => xScale(d.x))
      .attr('cy', (d) => yScale(d.y))
      .attr('fill', METRIC_COLORS[yMetric])
      .attr('fill-opacity', 0.7)
      .attr('stroke', 'var(--surface-panel)')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .on('mouseenter', function (event, d) {
        d3.select(this).attr('r', 8).attr('fill-opacity', 1);

        showGlobalChartTooltip(
          event,
          `
            ${d.label ? `<strong>${d.label}</strong><br/>` : ''}
            ${d.date ? `${d.date}<br/>` : ''}
            ${METRIC_LABELS[xMetric]}: ${d.x.toFixed(3)}<br/>
            ${METRIC_LABELS[yMetric]}: ${d.y.toFixed(3)}
          `,
          { offsetX: 15, offsetY: -15 }
        );
      })
      .on('mouseleave', function () {
        d3.select(this).attr('r', 6).attr('fill-opacity', 0.7);
        hideGlobalChartTooltip();
      });

    // Apply animation only if not reduced motion, without staggered delays
    if (prefersReducedMotion) {
      pointSelection.attr('r', 6);
    } else {
      pointSelection
        .attr('r', 0)
        .transition()
        .duration(300)
        .attr('r', 6);
    }

    // Title
    svg
      .append('text')
      .attr('x', width / 2)
      .attr('y', 24)
      .attr('text-anchor', 'middle')
      .attr('fill', 'var(--text-primary)')
      .attr('font-family', 'var(--font-display)')
      .attr('font-size', '16px')
      .text(`${METRIC_LABELS[xMetric]} vs ${METRIC_LABELS[yMetric]}`);

    // Cleanup function to prevent memory leaks
    return () => {
      svg.selectAll('*').interrupt();
      svg.selectAll('*').on('.', null); // Remove all event listeners
    };
  }, [data, xMetric, yMetric, width, height, showTrendline, hasData]);

  // Show message when no data is available
  if (!hasData) {
    return (
      <div className="chart-wrapper correlation-chart" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height, color: '#78716C' }}>
        <div style={{ textAlign: 'center' }}>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ opacity: 0.5, marginBottom: '12px' }}>
            <circle cx="7.5" cy="7.5" r="2.5" />
            <circle cx="16.5" cy="16.5" r="2.5" />
            <path d="M7.5 16.5L16.5 7.5" />
          </svg>
          <p style={{ margin: 0, fontSize: '14px', fontWeight: 500 }}>No correlation data available</p>
          <p style={{ margin: '8px 0 0', fontSize: '12px', opacity: 0.7 }}>
            Requires collected data for both selected metrics
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="chart-wrapper correlation-chart">
      <svg ref={svgRef} width={width} height={height} />
    </div>
  );
}
