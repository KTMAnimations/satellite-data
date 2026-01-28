import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import type { SeasonalSummary, MetricType } from '../../types';
import './Charts.css';

interface SeasonalBarChartProps {
  data: SeasonalSummary;
  selectedMetrics?: MetricType[];
  width?: number;
  height?: number;
}

const METRIC_LABELS: Record<MetricType, string> = {
  ndvi: 'NDVI',
  nightlights: 'Nighttime Lights',
  urban_density: 'Urban Density',
  parking: 'Parking',
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

export function SeasonalBarChart({ data, selectedMetrics, width = 400, height = 300 }: SeasonalBarChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  // Prepare data - only include metrics that are selected AND have data in BOTH seasons
  // If no selectedMetrics provided, show all metrics that have data
  const allMetrics: MetricType[] = Object.keys(METRIC_LABELS) as MetricType[];
  const metricsToShow = selectedMetrics && selectedMetrics.length > 0 ? selectedMetrics : allMetrics;
  const chartData = metricsToShow
    .filter(
      (m) =>
        data.winter_avg[m] !== null &&
        data.winter_avg[m] !== undefined &&
        data.summer_avg[m] !== null &&
        data.summer_avg[m] !== undefined
    )
    .map((metric) => ({
      metric,
      winter: data.winter_avg[metric] || 0,
      summer: data.summer_avg[metric] || 0,
      change: data.change_pct[metric] || 0,
    }));

  useEffect(() => {
    const svgElement = svgRef.current;
    if (!svgElement) return;

    const svg = d3.select(svgElement);

    // Interrupt any ongoing transitions and clear previous content
    svg.selectAll('*').interrupt();
    svg.selectAll('*').remove();

    // Don't render chart if no data
    if (chartData.length === 0) return;

    const margin = { top: 20, right: 20, bottom: 60, left: 60 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

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

    // Winter bars - using teal
    groups
      .append('rect')
      .attr('x', x1Scale('winter') || 0)
      .attr('y', (d) => yScale(d.winter))
      .attr('width', x1Scale.bandwidth())
      .attr('height', (d) => innerHeight - yScale(d.winter))
      .attr('fill', '#0D9488')
      .attr('rx', 2);

    // Summer bars - using amber
    groups
      .append('rect')
      .attr('x', x1Scale('summer') || 0)
      .attr('y', (d) => yScale(d.summer))
      .attr('width', x1Scale.bandwidth())
      .attr('height', (d) => innerHeight - yScale(d.summer))
      .attr('fill', '#D97706')
      .attr('rx', 2);

    // Change labels
    groups
      .append('text')
      .attr('x', x0Scale.bandwidth() / 2)
      .attr('y', (d) => yScale(Math.max(d.winter, d.summer)) - 5)
      .attr('text-anchor', 'middle')
      .attr('font-size', '10px')
      .attr('font-weight', 'bold')
      .attr('fill', (d) => (d.change > 0 ? '#059669' : '#DC2626'))
      .text((d) => `${d.change > 0 ? '+' : ''}${d.change.toFixed(1)}%`);

    // Legend
    const legend = svg.append('g').attr('transform', `translate(${margin.left}, 5)`);

    legend
      .append('rect')
      .attr('width', 12)
      .attr('height', 12)
      .attr('fill', '#0D9488');

    legend.append('text').attr('x', 16).attr('y', 10).attr('font-size', '11px').attr('fill', '#57534E').text('Winter');

    legend
      .append('rect')
      .attr('x', 70)
      .attr('width', 12)
      .attr('height', 12)
      .attr('fill', '#D97706');

    legend.append('text').attr('x', 86).attr('y', 10).attr('font-size', '11px').attr('fill', '#57534E').text('Summer');

    // Cleanup function to prevent memory leaks
    return () => {
      svg.selectAll('*').interrupt();
      svg.selectAll('*').on('.', null); // Remove all event listeners
    };
  }, [chartData, width, height]);

  // Show message when no seasonal data is available
  if (chartData.length === 0) {
    return (
      <div className="chart-wrapper" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height, color: '#78716C' }}>
        <div style={{ textAlign: 'center' }}>
          <p style={{ margin: 0, fontSize: '14px' }}>No seasonal comparison available</p>
          <p style={{ margin: '8px 0 0', fontSize: '12px', opacity: 0.7 }}>
            Requires data from both winter (Dec-Feb) and summer (Jun-Aug) months
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
}
