import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import type { SeasonalSummary, MetricType } from '../../types';
import './Charts.css';

interface SeasonalBarChartProps {
  data: SeasonalSummary;
  width?: number;
  height?: number;
}

const METRIC_COLORS: Record<MetricType, string> = {
  ndvi: '#22c55e',
  nightlights: '#f59e0b',
  urban_density: '#8b5cf6',
  parking: '#3b82f6',
};

const METRIC_LABELS: Record<MetricType, string> = {
  ndvi: 'NDVI',
  nightlights: 'Nighttime Lights',
  urban_density: 'Urban Density',
  parking: 'Parking',
};

export function SeasonalBarChart({ data, width = 400, height = 300 }: SeasonalBarChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const margin = { top: 20, right: 20, bottom: 60, left: 60 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Prepare data
    const metrics: MetricType[] = ['nightlights', 'ndvi', 'urban_density', 'parking'];
    const chartData = metrics
      .filter(
        (m) =>
          data.winter_avg[m] !== null &&
          data.summer_avg[m] !== null
      )
      .map((metric) => ({
        metric,
        winter: data.winter_avg[metric] || 0,
        summer: data.summer_avg[metric] || 0,
        change: data.change_pct[metric] || 0,
      }));

    if (chartData.length === 0) return;

    // Scales
    const x0Scale = d3
      .scaleBand()
      .domain(chartData.map((d) => d.metric))
      .range([0, innerWidth])
      .padding(0.2);

    const x1Scale = d3
      .scaleBand()
      .domain(['winter', 'summer'])
      .range([0, x0Scale.bandwidth()])
      .padding(0.1);

    // Normalize values for comparison
    const maxValue = Math.max(
      ...chartData.flatMap((d) => [d.winter, d.summer])
    );

    const yScale = d3.scaleLinear().domain([0, maxValue * 1.1]).range([innerHeight, 0]);

    // X axis
    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x0Scale).tickFormat((d) => METRIC_LABELS[d as MetricType]))
      .selectAll('text')
      .attr('transform', 'rotate(-30)')
      .style('text-anchor', 'end');

    // Y axis
    g.append('g').call(d3.axisLeft(yScale).ticks(5));

    // Bars
    const groups = g
      .selectAll('.metric-group')
      .data(chartData)
      .enter()
      .append('g')
      .attr('class', 'metric-group')
      .attr('transform', (d) => `translate(${x0Scale(d.metric)},0)`);

    // Winter bars
    groups
      .append('rect')
      .attr('x', x1Scale('winter') || 0)
      .attr('y', (d) => yScale(d.winter))
      .attr('width', x1Scale.bandwidth())
      .attr('height', (d) => innerHeight - yScale(d.winter))
      .attr('fill', '#60a5fa')
      .attr('rx', 2);

    // Summer bars
    groups
      .append('rect')
      .attr('x', x1Scale('summer') || 0)
      .attr('y', (d) => yScale(d.summer))
      .attr('width', x1Scale.bandwidth())
      .attr('height', (d) => innerHeight - yScale(d.summer))
      .attr('fill', '#f97316')
      .attr('rx', 2);

    // Change labels
    groups
      .append('text')
      .attr('x', x0Scale.bandwidth() / 2)
      .attr('y', (d) => yScale(Math.max(d.winter, d.summer)) - 5)
      .attr('text-anchor', 'middle')
      .attr('font-size', '10px')
      .attr('font-weight', 'bold')
      .attr('fill', (d) => (d.change > 0 ? '#22c55e' : '#ef4444'))
      .text((d) => `${d.change > 0 ? '+' : ''}${d.change.toFixed(1)}%`);

    // Legend
    const legend = svg.append('g').attr('transform', `translate(${margin.left}, 5)`);

    legend
      .append('rect')
      .attr('width', 12)
      .attr('height', 12)
      .attr('fill', '#60a5fa');

    legend.append('text').attr('x', 16).attr('y', 10).attr('font-size', '11px').text('Winter');

    legend
      .append('rect')
      .attr('x', 70)
      .attr('width', 12)
      .attr('height', 12)
      .attr('fill', '#f97316');

    legend.append('text').attr('x', 86).attr('y', 10).attr('font-size', '11px').text('Summer');
  }, [data, width, height]);

  return (
    <div className="chart-wrapper">
      <svg ref={svgRef} width={width} height={height} />
    </div>
  );
}
