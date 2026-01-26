import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import type { MetricType } from '../../types';
import './SmallMultiples.css';

interface RegionData {
  regionId: string;
  regionName: string;
  data: { date: string; value: number }[];
}

interface SmallMultiplesProps {
  regions: RegionData[];
  metric: MetricType;
  columns?: number;
  cellWidth?: number;
  cellHeight?: number;
  onRegionClick?: (regionId: string) => void;
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

export function SmallMultiples({
  regions,
  metric,
  columns = 3,
  cellWidth = 250,
  cellHeight = 150,
  onRegionClick,
}: SmallMultiplesProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || regions.length === 0) return;

    const container = d3.select(containerRef.current);
    container.selectAll('*').remove();

    // Calculate global scales for consistency
    const allDates: Date[] = [];
    const allValues: number[] = [];

    regions.forEach((region) => {
      region.data.forEach((d) => {
        allDates.push(new Date(d.date));
        allValues.push(d.value);
      });
    });

    const xDomain = d3.extent(allDates) as [Date, Date];
    const yDomain = [
      Math.min(...allValues) * 0.9,
      Math.max(...allValues) * 1.1,
    ];

    const margin = { top: 25, right: 10, bottom: 25, left: 35 };
    const innerWidth = cellWidth - margin.left - margin.right;
    const innerHeight = cellHeight - margin.top - margin.bottom;

    const xScale = d3.scaleTime().domain(xDomain).range([0, innerWidth]);
    const yScale = d3.scaleLinear().domain(yDomain).range([innerHeight, 0]);

    // Create cells
    regions.forEach((region) => {
      const cell = container
        .append('div')
        .attr('class', 'small-multiple-cell')
        .style('cursor', onRegionClick ? 'pointer' : 'default')
        .on('click', () => onRegionClick?.(region.regionId));

      const svg = cell.append('svg').attr('width', cellWidth).attr('height', cellHeight);

      const g = svg
        .append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

      // Background
      g.append('rect')
        .attr('width', innerWidth)
        .attr('height', innerHeight)
        .attr('fill', 'var(--surface-recessed)')
        .attr('rx', 4);

      // Title
      svg
        .append('text')
        .attr('x', cellWidth / 2)
        .attr('y', 16)
        .attr('text-anchor', 'middle')
        .attr('fill', 'var(--text-primary)')
        .attr('font-family', 'var(--font-body)')
        .attr('font-size', '11px')
        .attr('font-weight', '500')
        .text(region.regionName.length > 20 ? region.regionName.slice(0, 20) + '...' : region.regionName);

      if (region.data.length === 0) {
        g.append('text')
          .attr('x', innerWidth / 2)
          .attr('y', innerHeight / 2)
          .attr('text-anchor', 'middle')
          .attr('fill', 'var(--text-tertiary)')
          .attr('font-size', '10px')
          .text('No data');
        return;
      }

      // Area
      const area = d3
        .area<{ date: string; value: number }>()
        .x((d) => xScale(new Date(d.date)))
        .y0(innerHeight)
        .y1((d) => yScale(d.value))
        .curve(d3.curveMonotoneX);

      g.append('path')
        .datum(region.data)
        .attr('fill', METRIC_COLORS[metric])
        .attr('fill-opacity', 0.2)
        .attr('d', area);

      // Line
      const line = d3
        .line<{ date: string; value: number }>()
        .x((d) => xScale(new Date(d.date)))
        .y((d) => yScale(d.value))
        .curve(d3.curveMonotoneX);

      g.append('path')
        .datum(region.data)
        .attr('fill', 'none')
        .attr('stroke', METRIC_COLORS[metric])
        .attr('stroke-width', 2)
        .attr('d', line);

      // Min/Max indicators
      const sortedByValue = [...region.data].sort((a, b) => a.value - b.value);
      const min = sortedByValue[0];
      const max = sortedByValue[sortedByValue.length - 1];

      // Min point
      g.append('circle')
        .attr('cx', xScale(new Date(min.date)))
        .attr('cy', yScale(min.value))
        .attr('r', 3)
        .attr('fill', 'var(--metric-alert)');

      // Max point
      g.append('circle')
        .attr('cx', xScale(new Date(max.date)))
        .attr('cy', yScale(max.value))
        .attr('r', 3)
        .attr('fill', 'var(--metric-quaternary)');

      // Simple x-axis
      g.append('line')
        .attr('x1', 0)
        .attr('x2', innerWidth)
        .attr('y1', innerHeight)
        .attr('y2', innerHeight)
        .attr('stroke', 'var(--border-default)');

      // Value labels
      g.append('text')
        .attr('x', innerWidth - 5)
        .attr('y', innerHeight + 14)
        .attr('text-anchor', 'end')
        .attr('fill', 'var(--text-tertiary)')
        .attr('font-family', 'var(--font-mono)')
        .attr('font-size', '9px')
        .text(region.data[region.data.length - 1].value.toFixed(2));
    });
  }, [regions, metric, columns, cellWidth, cellHeight, onRegionClick]);

  return (
    <div className="small-multiples">
      <div className="small-multiples-header">
        <h4>{METRIC_LABELS[metric]} Comparison</h4>
        <span className="badge badge-cyan">{regions.length} regions</span>
      </div>
      <div
        ref={containerRef}
        className="small-multiples-grid"
        style={{
          gridTemplateColumns: `repeat(${columns}, ${cellWidth}px)`,
        }}
      />
    </div>
  );
}
