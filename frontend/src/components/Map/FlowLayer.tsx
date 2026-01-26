import { useEffect, useRef, useMemo } from 'react';
import { useMap } from 'react-leaflet';
import * as d3 from 'd3';
import './FlowLayer.css';

export interface FlowPoint {
  id: string;
  name: string;
  lat: number;
  lng: number;
  value: number; // Activity level (e.g., nightlights intensity)
}

export interface FlowConnection {
  source: FlowPoint;
  target: FlowPoint;
  intensity: number; // Flow strength (0-1)
}

interface FlowLayerProps {
  /** Array of location points with their activity values */
  points: FlowPoint[];
  /** Optional explicit connections, otherwise inferred from value changes */
  connections?: FlowConnection[];
  /** Whether to show animated particles */
  animated?: boolean;
  /** Animation speed multiplier (default: 1) */
  speed?: number;
  /** Particle count per flow (default: 5) */
  particleCount?: number;
  /** Flow color (default: #3B82F6) */
  color?: string;
  /** Whether to show point labels */
  showLabels?: boolean;
  /** Minimum intensity threshold to show flow (default: 0.1) */
  minIntensity?: number;
}

/**
 * FlowLayer - Animated migration flow visualization on Leaflet maps.
 *
 * Displays animated particles flowing between locations to visualize
 * migration patterns (e.g., snowbird migration from Northeast to Florida).
 *
 * Usage:
 * ```tsx
 * <FlowLayer
 *   points={[
 *     { id: 'nyc', name: 'New York', lat: 40.7, lng: -74.0, value: 0.3 },
 *     { id: 'miami', name: 'Miami', lat: 25.7, lng: -80.2, value: 0.8 },
 *   ]}
 *   animated={true}
 *   speed={1.5}
 * />
 * ```
 */
export function FlowLayer({
  points,
  connections: explicitConnections,
  animated = true,
  speed = 1,
  particleCount = 5,
  color = '#3B82F6',
  showLabels = true,
  minIntensity = 0.1,
}: FlowLayerProps) {
  const map = useMap();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const animationRef = useRef<number | null>(null);

  // Infer connections from point values if not provided
  const connections = useMemo(() => {
    if (explicitConnections) return explicitConnections;

    // Sort points by value (low to high)
    const sorted = [...points].sort((a, b) => a.value - b.value);

    // Create flows from low-value to high-value regions
    const flows: FlowConnection[] = [];
    const avgValue = points.reduce((sum, p) => sum + p.value, 0) / points.length;

    for (const source of sorted) {
      if (source.value >= avgValue) continue; // Skip high-value sources

      for (const target of sorted) {
        if (target.value <= avgValue) continue; // Skip low-value targets
        if (source.id === target.id) continue;

        // Intensity based on value difference
        const maxDiff = Math.max(...points.map((p) => p.value)) - Math.min(...points.map((p) => p.value));
        const intensity = maxDiff > 0 ? (target.value - source.value) / maxDiff : 0;

        if (intensity >= minIntensity) {
          flows.push({ source, target, intensity });
        }
      }
    }

    return flows;
  }, [points, explicitConnections, minIntensity]);

  // Create or update SVG overlay
  useEffect(() => {
    if (!map || connections.length === 0) return;

    // Create SVG pane if it doesn't exist
    let pane = map.getPane('flowPane');
    if (!pane) {
      pane = map.createPane('flowPane');
      pane.style.zIndex = '450'; // Above tiles, below markers
    }

    // Create SVG element
    const bounds = map.getBounds();
    const size = map.getSize();

    if (!svgRef.current) {
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('class', 'flow-layer-svg');
      svg.style.position = 'absolute';
      svg.style.pointerEvents = 'none';
      pane.appendChild(svg);
      svgRef.current = svg;
    }

    const svg = d3.select(svgRef.current);

    // Update SVG position and size
    const topLeft = map.latLngToLayerPoint(bounds.getNorthWest());
    svgRef.current.style.left = `${topLeft.x}px`;
    svgRef.current.style.top = `${topLeft.y}px`;
    svgRef.current.setAttribute('width', `${size.x}`);
    svgRef.current.setAttribute('height', `${size.y}`);

    // Clear previous content
    svg.selectAll('*').remove();

    // Create defs for arrow markers
    const defs = svg.append('defs');

    defs
      .append('marker')
      .attr('id', 'flow-arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 8)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', color)
      .attr('opacity', 0.6);

    // Create group for flows
    const flowGroup = svg.append('g').attr('class', 'flows');

    // Draw flow paths
    connections.forEach((conn) => {
      const sourcePoint = map.latLngToLayerPoint([conn.source.lat, conn.source.lng]);
      const targetPoint = map.latLngToLayerPoint([conn.target.lat, conn.target.lng]);

      // Offset from top-left
      const x1 = sourcePoint.x - topLeft.x;
      const y1 = sourcePoint.y - topLeft.y;
      const x2 = targetPoint.x - topLeft.x;
      const y2 = targetPoint.y - topLeft.y;

      // Calculate curved path (quadratic bezier)
      const midX = (x1 + x2) / 2;
      const midY = (y1 + y2) / 2;
      const dx = x2 - x1;
      const dy = y2 - y1;
      const dist = Math.sqrt(dx * dx + dy * dy);

      // Curve offset perpendicular to the line
      const curveOffset = dist * 0.2;
      const nx = -dy / dist;
      const ny = dx / dist;
      const ctrlX = midX + nx * curveOffset;
      const ctrlY = midY + ny * curveOffset;

      const pathData = `M ${x1} ${y1} Q ${ctrlX} ${ctrlY} ${x2} ${y2}`;

      // Draw the flow path
      const path = flowGroup
        .append('path')
        .attr('d', pathData)
        .attr('fill', 'none')
        .attr('stroke', color)
        .attr('stroke-width', Math.max(1, conn.intensity * 4))
        .attr('stroke-opacity', 0.3 + conn.intensity * 0.4)
        .attr('marker-end', 'url(#flow-arrow)')
        .attr('class', 'flow-path');

      // Add animated particles if enabled
      if (animated) {
        const pathLength = (path.node() as SVGPathElement).getTotalLength();

        for (let p = 0; p < particleCount; p++) {
          const particle = flowGroup
            .append('circle')
            .attr('r', 3 + conn.intensity * 2)
            .attr('fill', color)
            .attr('opacity', 0.8)
            .attr('class', 'flow-particle');

          // Animate along path
          const duration = (8000 / speed) * (1 - conn.intensity * 0.5);
          const delay = (duration / particleCount) * p;

          const animate = () => {
            particle
              .attr('opacity', 0)
              .transition()
              .delay(delay)
              .duration(0)
              .attr('opacity', 0.8)
              .transition()
              .duration(duration)
              .ease(d3.easeLinear)
              .attrTween('transform', () => {
                return (t: number) => {
                  const point = (path.node() as SVGPathElement).getPointAtLength(t * pathLength);
                  return `translate(${point.x}, ${point.y})`;
                };
              })
              .attr('opacity', 0.2)
              .on('end', animate);
          };

          animate();
        }
      }
    });

    // Draw points
    const pointGroup = svg.append('g').attr('class', 'points');

    points.forEach((point) => {
      const pos = map.latLngToLayerPoint([point.lat, point.lng]);
      const x = pos.x - topLeft.x;
      const y = pos.y - topLeft.y;

      // Point circle
      pointGroup
        .append('circle')
        .attr('cx', x)
        .attr('cy', y)
        .attr('r', 6 + point.value * 8)
        .attr('fill', color)
        .attr('fill-opacity', 0.6 + point.value * 0.3)
        .attr('stroke', '#fff')
        .attr('stroke-width', 2)
        .attr('class', 'flow-point');

      // Label
      if (showLabels) {
        pointGroup
          .append('text')
          .attr('x', x)
          .attr('y', y - 12 - point.value * 8)
          .attr('text-anchor', 'middle')
          .attr('fill', '#fff')
          .attr('font-size', '11px')
          .attr('font-weight', '500')
          .attr('class', 'flow-label')
          .text(point.name);

        // Value indicator
        const changeText = point.value > 0.5 ? `+${((point.value - 0.5) * 100).toFixed(0)}%` : `${((point.value - 0.5) * 100).toFixed(0)}%`;
        pointGroup
          .append('text')
          .attr('x', x)
          .attr('y', y + 20 + point.value * 8)
          .attr('text-anchor', 'middle')
          .attr('fill', point.value > 0.5 ? '#22C55E' : '#EF4444')
          .attr('font-size', '10px')
          .attr('font-family', 'var(--font-mono)')
          .attr('class', 'flow-value')
          .text(changeText);
      }
    });

    // Update on map move/zoom
    const updatePosition = () => {
      const newBounds = map.getBounds();
      const newTopLeft = map.latLngToLayerPoint(newBounds.getNorthWest());
      const newSize = map.getSize();

      if (svgRef.current) {
        svgRef.current.style.left = `${newTopLeft.x}px`;
        svgRef.current.style.top = `${newTopLeft.y}px`;
        svgRef.current.setAttribute('width', `${newSize.x}`);
        svgRef.current.setAttribute('height', `${newSize.y}`);
      }

      // Redraw paths and points at new positions
      // For efficiency, we just update transforms rather than redrawing
      flowGroup.selectAll('.flow-path').each(function (_d, i) {
        const conn = connections[i];
        if (!conn) return;

        const sourcePoint = map.latLngToLayerPoint([conn.source.lat, conn.source.lng]);
        const targetPoint = map.latLngToLayerPoint([conn.target.lat, conn.target.lng]);

        const x1 = sourcePoint.x - newTopLeft.x;
        const y1 = sourcePoint.y - newTopLeft.y;
        const x2 = targetPoint.x - newTopLeft.x;
        const y2 = targetPoint.y - newTopLeft.y;

        const midX = (x1 + x2) / 2;
        const midY = (y1 + y2) / 2;
        const dx = x2 - x1;
        const dy = y2 - y1;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const curveOffset = dist * 0.2;
        const nx = -dy / dist;
        const ny = dx / dist;
        const ctrlX = midX + nx * curveOffset;
        const ctrlY = midY + ny * curveOffset;

        const pathData = `M ${x1} ${y1} Q ${ctrlX} ${ctrlY} ${x2} ${y2}`;
        d3.select(this).attr('d', pathData);
      });

      pointGroup.selectAll('.flow-point').each(function (_d, i) {
        const point = points[i];
        if (!point) return;

        const pos = map.latLngToLayerPoint([point.lat, point.lng]);
        const x = pos.x - newTopLeft.x;
        const y = pos.y - newTopLeft.y;

        d3.select(this).attr('cx', x).attr('cy', y);
      });
    };

    map.on('move', updatePosition);
    map.on('zoom', updatePosition);

    return () => {
      map.off('move', updatePosition);
      map.off('zoom', updatePosition);

      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }

      if (svgRef.current && svgRef.current.parentNode) {
        svgRef.current.parentNode.removeChild(svgRef.current);
        svgRef.current = null;
      }
    };
  }, [map, connections, points, animated, speed, particleCount, color, showLabels]);

  return null;
}

// Helper function to create flow data from region metrics
export function createFlowData(
  regions: Array<{ id: string; name: string; lat: number; lng: number }>,
  winterValues: Record<string, number>,
  summerValues: Record<string, number>
): FlowPoint[] {
  return regions.map((region) => {
    const winter = winterValues[region.id] || 0;
    const summer = summerValues[region.id] || 0;
    const total = winter + summer || 1;

    // Normalize: 0 = all summer activity, 1 = all winter activity
    const value = winter / total;

    return {
      id: region.id,
      name: region.name,
      lat: region.lat,
      lng: region.lng,
      value,
    };
  });
}
