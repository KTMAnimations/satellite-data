import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import type { MetricType } from '../../types';
import './Charts.css';

interface RegionRank {
  regionId: string;
  regionName: string;
  value: number;
  change?: number;
}

interface RegionalRankingChartProps {
  data: RegionRank[];
  metric: MetricType;
  title?: string;
  width?: number;
  height?: number;
  maxItems?: number;
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

export function RegionalRankingChart({
  data,
  metric,
  title = 'Regional Ranking',
  width = 400,
  height = 400,
  maxItems = 10,
  onRegionClick,
}: RegionalRankingChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || data.length === 0) return;

    const svg = d3.select(svgRef.current);

    // Interrupt any ongoing transitions and clear previous content
    svg.selectAll('*').interrupt();
    svg.selectAll('*').remove();

    const margin = { top: 40, right: 100, bottom: 20, left: 120 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Sort and limit data
    const sortedData = [...data]
      .sort((a, b) => b.value - a.value)
      .slice(0, maxItems);

    // Scales
    const yScale = d3
      .scaleBand()
      .domain(sortedData.map((d) => d.regionName))
      .range([0, innerHeight])
      .padding(0.25);

    const xMax = d3.max(sortedData, (d) => d.value) || 0;
    const xScale = d3.scaleLinear().domain([0, xMax * 1.1]).range([0, innerWidth]);

    // Color scale for ranking
    const colorScale = d3
      .scaleLinear<string>()
      .domain([0, sortedData.length - 1])
      .range([METRIC_COLORS[metric], d3.color(METRIC_COLORS[metric])!.darker(1.5).toString()]);

    // Bars
    const barGroups = g
      .selectAll('.bar-group')
      .data(sortedData)
      .enter()
      .append('g')
      .attr('class', 'bar-group')
      .style('cursor', onRegionClick ? 'pointer' : 'default')
      .on('click', (_, d) => onRegionClick?.(d.regionId))
      .on('mouseenter', function () {
        d3.select(this).select('rect').attr('opacity', 0.8);
      })
      .on('mouseleave', function () {
        d3.select(this).select('rect').attr('opacity', 1);
      });

    // Rank numbers
    barGroups
      .append('text')
      .attr('x', -10)
      .attr('y', (d) => (yScale(d.regionName) || 0) + yScale.bandwidth() / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'end')
      .attr('fill', 'var(--text-tertiary)')
      .attr('font-family', 'var(--font-mono)')
      .attr('font-size', '11px')
      .text((_, i) => `#${i + 1}`);

    // Region labels
    barGroups
      .append('text')
      .attr('x', -15)
      .attr('y', (d) => (yScale(d.regionName) || 0) + yScale.bandwidth() / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'end')
      .attr('fill', 'var(--text-secondary)')
      .attr('font-family', 'var(--font-body)')
      .attr('font-size', '12px')
      .text((d) => {
        const name = d.regionName;
        return name.length > 12 ? name.slice(0, 12) + '...' : name;
      });

    // Bars with animation
    barGroups
      .append('rect')
      .attr('y', (d) => yScale(d.regionName) || 0)
      .attr('height', yScale.bandwidth())
      .attr('x', 0)
      .attr('width', 0)
      .attr('fill', (_, i) => colorScale(i))
      .attr('rx', 4)
      .transition()
      .duration(600)
      .delay((_, i) => i * 50)
      .attr('width', (d) => xScale(d.value));

    // Value labels
    barGroups
      .append('text')
      .attr('y', (d) => (yScale(d.regionName) || 0) + yScale.bandwidth() / 2)
      .attr('x', (d) => xScale(d.value) + 8)
      .attr('dy', '0.35em')
      .attr('fill', 'var(--text-secondary)')
      .attr('font-family', 'var(--font-mono)')
      .attr('font-size', '11px')
      .text((d) => d.value.toFixed(3))
      .style('opacity', 0)
      .transition()
      .duration(300)
      .delay((_, i) => i * 50 + 400)
      .style('opacity', 1);

    // Change indicators
    barGroups
      .filter((d) => d.change !== undefined)
      .append('text')
      .attr('y', (d) => (yScale(d.regionName) || 0) + yScale.bandwidth() / 2)
      .attr('x', (d) => xScale(d.value) + 55)
      .attr('dy', '0.35em')
      .attr('fill', (d) =>
        (d.change || 0) >= 0 ? 'var(--metric-quaternary)' : 'var(--metric-alert)'
      )
      .attr('font-family', 'var(--font-mono)')
      .attr('font-size', '10px')
      .text((d) => {
        const change = d.change || 0;
        return `${change >= 0 ? '+' : ''}${change.toFixed(1)}%`;
      })
      .style('opacity', 0)
      .transition()
      .duration(300)
      .delay((_, i) => i * 50 + 600)
      .style('opacity', 1);

    // Title
    svg
      .append('text')
      .attr('x', width / 2)
      .attr('y', 24)
      .attr('text-anchor', 'middle')
      .attr('fill', 'var(--text-primary)')
      .attr('font-family', 'var(--font-display)')
      .attr('font-size', '16px')
      .text(title);

    // Cleanup function to prevent memory leaks
    return () => {
      if (svgRef.current) {
        const svg = d3.select(svgRef.current);
        svg.selectAll('*').interrupt();
        svg.selectAll('*').on('.', null); // Remove all event listeners
      }
    };
  }, [data, metric, title, width, height, maxItems, onRegionClick]);

  return (
    <div className="chart-wrapper ranking-chart">
      <svg ref={svgRef} width={width} height={height} />
    </div>
  );
}
