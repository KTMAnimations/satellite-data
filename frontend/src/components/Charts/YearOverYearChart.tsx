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
};

const METRIC_LABELS: Record<MetricType, string> = {
  ndvi: 'NDVI',
  nightlights: 'Nighttime Lights',
  urban_density: 'Urban Density',
  parking: 'Parking Occupancy',
};

export function YearOverYearChart({
  data,
  selectedMetric,
  width = 500,
  height = 300,
}: YearOverYearChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current) return;

    const metricData = data[selectedMetric];
    if (!metricData || metricData.length === 0) return;

    const svg = d3.select(svgRef.current);
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

    // Bars
    const bars = g.selectAll('.bar').data(sortedData);

    bars
      .enter()
      .append('rect')
      .attr('class', 'bar')
      .attr('y', (d) => yScale(String(d.year)) || 0)
      .attr('height', yScale.bandwidth())
      .attr('x', 0)
      .attr('width', 0)
      .attr('fill', METRIC_COLORS[selectedMetric])
      .attr('rx', 4)
      .transition()
      .duration(600)
      .delay((_, i) => i * 100)
      .attr('width', (d) => xScale(d.value));

    // Values at end of bars
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
      .text((d) => d.value.toFixed(3))
      .style('opacity', 0)
      .transition()
      .duration(400)
      .delay((_, i) => i * 100 + 300)
      .style('opacity', 1);

    // Year-over-year change indicators
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
        .text(`${isPositive ? '+' : ''}${change.toFixed(1)}%`)
        .style('opacity', 0)
        .transition()
        .duration(400)
        .delay(i * 100 + 500)
        .style('opacity', 1);
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
  }, [data, selectedMetric, width, height]);

  return (
    <div className="chart-wrapper yoy-chart">
      <svg ref={svgRef} width={width} height={height} />
    </div>
  );
}
