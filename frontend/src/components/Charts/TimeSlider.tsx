import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import './TimeSlider.css';

const SLIDER_MARGIN = { left: 40, right: 40, top: 20, bottom: 30 } as const;
const COMPACT_SLIDER_MARGIN = { left: 28, right: 28, top: 14, bottom: 14 } as const;

interface TimeSliderProps {
  dates: Date[];
  selectedDate: Date;
  onDateChange: (date: Date) => void;
  isPlaying?: boolean;
  playbackBlocked?: boolean;
  onPlayPause?: () => void;
  playbackSpeed?: number;
  onSpeedChange?: (speed: number) => void;
  width?: number;
  density?: 'regular' | 'compact';
}

export function TimeSlider({
  dates,
  selectedDate,
  onDateChange,
  isPlaying = false,
  playbackBlocked = false,
  onPlayPause,
  playbackSpeed = 1,
  onSpeedChange,
  width = 600,
  density = 'regular',
}: TimeSliderProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const isCompact = density === 'compact';
  const showAxis = !isCompact;
  const height = isCompact ? 56 : 80;
  const margin = isCompact ? COMPACT_SLIDER_MARGIN : SLIDER_MARGIN;
  const innerWidth = width - margin.left - margin.right;
  const trackY = isCompact ? 12 : 15;
  const thumbRadius = isCompact ? 8 : 10;
  const thumbStrokeWidth = isCompact ? 2.5 : 3;
  const overlayHeight = isCompact ? 28 : 40;

  const sortedDates = useMemo(
    () => [...dates].sort((a, b) => a.getTime() - b.getTime()),
    [dates]
  );

  const xScale = useMemo(() => {
    const [minDate, maxDate] = d3.extent(sortedDates);
    const domainStart = minDate ?? selectedDate;
    const domainEnd = maxDate ?? selectedDate;

    return d3
      .scaleTime()
      .domain([domainStart, domainEnd])
      .range([0, innerWidth]);
  }, [sortedDates, innerWidth, selectedDate]);

  const findClosestDate = useCallback(
    (x: number) => {
      if (sortedDates.length === 0) return selectedDate;

      const targetDate = xScale.invert(x);
      let closest = sortedDates[0];
      let minDiff = Math.abs(targetDate.getTime() - closest.getTime());

      for (const date of sortedDates) {
        const diff = Math.abs(targetDate.getTime() - date.getTime());
        if (diff < minDiff) {
          minDiff = diff;
          closest = date;
        }
      }
      return closest;
    },
    [sortedDates, xScale, selectedDate]
  );

  useEffect(() => {
    const svgElement = svgRef.current;
    if (!svgElement || sortedDates.length === 0) return;

    const svg = d3.select(svgElement);

    // Interrupt any ongoing transitions and clear previous content
    svg.selectAll('*').interrupt();
    svg.selectAll('*').remove();

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Track background
    g.append('rect')
      .attr('class', 'slider-track')
      .attr('x', 0)
      .attr('y', trackY)
      .attr('width', innerWidth)
      .attr('height', 6)
      .attr('rx', 3)
      .attr('fill', 'var(--surface-recessed)');

    // Progress fill
    const selectedX = xScale(selectedDate);
    g.append('rect')
      .attr('class', 'slider-progress')
      .attr('x', 0)
      .attr('y', trackY)
      .attr('width', selectedX)
      .attr('height', 6)
      .attr('rx', 3)
      .attr('fill', 'var(--accent-primary)');

    // Date markers
    const tickDates = sortedDates.filter((_, i) =>
      i === 0 || i === sortedDates.length - 1 || i % Math.ceil(sortedDates.length / 6) === 0
    );

    tickDates.forEach((date) => {
      const x = xScale(date);
      g.append('line')
        .attr('x1', x)
        .attr('x2', x)
        .attr('y1', trackY - 3)
        .attr('y2', trackY + 9)
        .attr('stroke', 'var(--border-default)')
        .attr('stroke-width', 1);
    });

    // Determine appropriate tick format based on date granularity
    const dateSpanDays = sortedDates.length > 1
      ? (sortedDates[sortedDates.length - 1].getTime() - sortedDates[0].getTime()) / (1000 * 60 * 60 * 24)
      : 0;
    const avgGapDays = sortedDates.length > 1
      ? dateSpanDays / (sortedDates.length - 1)
      : 30;

    // Choose format based on granularity
    const tickFormat = avgGapDays <= 14
      ? d3.timeFormat('%b %d')   // Daily/weekly: "Jan 15"
      : d3.timeFormat('%b %Y');  // Monthly: "Jan 2024"
    const labelFormat = avgGapDays <= 14
      ? d3.timeFormat('%b %d, %Y')  // Daily/weekly: "Jan 15, 2024"
      : d3.timeFormat('%b %Y');     // Monthly: "Jan 2024"

    if (showAxis) {
      // Axis
      const xAxis = d3
        .axisBottom(xScale)
        .ticks(Math.min(sortedDates.length, 6))
        .tickFormat((d) => tickFormat(d as Date));

      g.append('g')
        .attr('class', 'axis')
        .attr('transform', `translate(0, 35)`)
        .call(xAxis);
    }

    // Thumb
    const thumb = g.append('g').attr('class', 'slider-thumb');

    thumb
      .append('circle')
      .attr('cx', selectedX)
      .attr('cy', trackY + 3)
      .attr('r', thumbRadius)
      .attr('fill', 'var(--accent-primary)')
      .attr('stroke', 'var(--surface-panel)')
      .attr('stroke-width', thumbStrokeWidth)
      .style('cursor', 'grab')
      .style('filter', 'drop-shadow(0 2px 4px rgba(0,0,0,0.3))');

    // Date label above thumb
    thumb
      .append('text')
      .attr('x', selectedX)
      .attr('y', -2)
      .attr('text-anchor', 'middle')
      .attr('font-family', 'var(--font-mono)')
      .attr('font-size', isCompact ? '10px' : '11px')
      .attr('fill', 'var(--text-primary)')
      .text(labelFormat(selectedDate));

    // Interactive overlay
    const overlay = g
      .append('rect')
      .attr('class', 'slider-overlay')
      .attr('x', 0)
      .attr('y', 0)
      .attr('width', innerWidth)
      .attr('height', overlayHeight)
      .attr('fill', 'transparent')
      .style('cursor', 'pointer');

    // Store reference (for potential future use)
    const trackElement = g.node();
    if (trackElement) {
      // trackRef is available for external access if needed
    }

    // Drag behavior - get coordinates relative to SVG then subtract margin
    const drag = d3
      .drag<SVGRectElement, unknown>()
      .on('start', () => setIsDragging(true))
      .on('drag', (event) => {
        // Get pointer relative to SVG element, then subtract left margin
        const [svgX] = d3.pointer(event.sourceEvent, svg.node());
        const x = Math.max(0, Math.min(innerWidth, svgX - margin.left));
        const closestDate = findClosestDate(x);
        onDateChange(closestDate);
      })
      .on('end', () => setIsDragging(false));

    overlay.call(drag);

    // Click to jump - get coordinates relative to SVG then subtract margin
    overlay.on('click', (event) => {
      const [svgX] = d3.pointer(event, svg.node());
      const x = Math.max(0, Math.min(innerWidth, svgX - margin.left));
      const closestDate = findClosestDate(x);
      onDateChange(closestDate);
    });

    // Cleanup function to prevent memory leaks
    return () => {
      svg.selectAll('*').interrupt();
      svg.selectAll('*').on('.', null); // Remove all event listeners
    };
  }, [findClosestDate, innerWidth, isCompact, margin.left, margin.top, onDateChange, selectedDate, showAxis, sortedDates, trackY, thumbRadius, thumbStrokeWidth, overlayHeight, xScale]);

  // Playback effect
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      if (playbackBlocked) return;
      const currentIndex = sortedDates.findIndex(
        (d) => d.getTime() === selectedDate.getTime()
      );
      const nextIndex = (currentIndex + 1) % sortedDates.length;
      onDateChange(sortedDates[nextIndex]);
    }, 1000 / playbackSpeed);

    return () => clearInterval(interval);
  }, [isPlaying, playbackBlocked, selectedDate, sortedDates, playbackSpeed, onDateChange]);

  return (
    <div className={`time-slider ${isCompact ? 'compact' : ''}`}>
      <div className="time-slider-controls">
        {onPlayPause && (
          <button
            className={`play-btn ${isPlaying ? 'playing' : ''}`}
            onClick={onPlayPause}
            aria-label={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="4" width="4" height="16" rx="1" />
                <rect x="14" y="4" width="4" height="16" rx="1" />
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5.14v14.72a1 1 0 001.5.86l11-7.36a1 1 0 000-1.72l-11-7.36a1 1 0 00-1.5.86z" />
              </svg>
            )}
          </button>
        )}

        {onSpeedChange && (
          <div className="speed-control">
            <label>Speed</label>
            <select
              value={playbackSpeed}
              onChange={(e) => onSpeedChange(Number(e.target.value))}
            >
              <option value={0.5}>0.5x</option>
              <option value={1}>1x</option>
              <option value={2}>2x</option>
              <option value={4}>4x</option>
            </select>
          </div>
        )}
      </div>

      <svg
        ref={svgRef}
        width={width}
        height={height}
        className={isDragging ? 'dragging' : ''}
      />
    </div>
  );
}
