import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import './TimeSlider.css';

interface TimeSliderProps {
  dates: Date[];
  selectedDate: Date;
  onDateChange: (date: Date) => void;
  isPlaying?: boolean;
  onPlayPause?: () => void;
  playbackSpeed?: number;
  onSpeedChange?: (speed: number) => void;
  width?: number;
}

export function TimeSlider({
  dates,
  selectedDate,
  onDateChange,
  isPlaying = false,
  onPlayPause,
  playbackSpeed = 1,
  onSpeedChange,
  width = 600,
}: TimeSliderProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const height = 80;
  const margin = { left: 40, right: 40, top: 20, bottom: 30 };
  const innerWidth = width - margin.left - margin.right;

  const sortedDates = [...dates].sort((a, b) => a.getTime() - b.getTime());

  const xScale = d3
    .scaleTime()
    .domain(d3.extent(sortedDates) as [Date, Date])
    .range([0, innerWidth]);

  const findClosestDate = useCallback(
    (x: number) => {
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
    [sortedDates, xScale]
  );

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Track background
    g.append('rect')
      .attr('class', 'slider-track')
      .attr('x', 0)
      .attr('y', 15)
      .attr('width', innerWidth)
      .attr('height', 6)
      .attr('rx', 3)
      .attr('fill', 'var(--surface-recessed)');

    // Progress fill
    const selectedX = xScale(selectedDate);
    g.append('rect')
      .attr('class', 'slider-progress')
      .attr('x', 0)
      .attr('y', 15)
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
        .attr('y1', 12)
        .attr('y2', 24)
        .attr('stroke', 'var(--border-default)')
        .attr('stroke-width', 1);
    });

    // Axis
    const xAxis = d3
      .axisBottom(xScale)
      .ticks(5)
      .tickFormat((d) => d3.timeFormat('%b %Y')(d as Date));

    g.append('g')
      .attr('class', 'axis')
      .attr('transform', `translate(0, 35)`)
      .call(xAxis);

    // Thumb
    const thumb = g.append('g').attr('class', 'slider-thumb');

    thumb
      .append('circle')
      .attr('cx', selectedX)
      .attr('cy', 18)
      .attr('r', 10)
      .attr('fill', 'var(--accent-primary)')
      .attr('stroke', 'var(--surface-panel)')
      .attr('stroke-width', 3)
      .style('cursor', 'grab')
      .style('filter', 'drop-shadow(0 2px 4px rgba(0,0,0,0.3))');

    // Date label above thumb
    thumb
      .append('text')
      .attr('x', selectedX)
      .attr('y', -2)
      .attr('text-anchor', 'middle')
      .attr('font-family', 'var(--font-mono)')
      .attr('font-size', '11px')
      .attr('fill', 'var(--text-primary)')
      .text(d3.timeFormat('%b %d, %Y')(selectedDate));

    // Interactive overlay
    const overlay = g
      .append('rect')
      .attr('class', 'slider-overlay')
      .attr('x', 0)
      .attr('y', 0)
      .attr('width', innerWidth)
      .attr('height', 40)
      .attr('fill', 'transparent')
      .style('cursor', 'pointer');

    // Store reference (for potential future use)
    const trackElement = g.node();
    if (trackElement) {
      // trackRef is available for external access if needed
    }

    // Drag behavior
    const drag = d3
      .drag<SVGRectElement, unknown>()
      .on('start', () => setIsDragging(true))
      .on('drag', (event) => {
        const x = Math.max(0, Math.min(innerWidth, event.x));
        const closestDate = findClosestDate(x);
        onDateChange(closestDate);
      })
      .on('end', () => setIsDragging(false));

    overlay.call(drag);

    // Click to jump
    overlay.on('click', (event) => {
      const [x] = d3.pointer(event);
      const closestDate = findClosestDate(x);
      onDateChange(closestDate);
    });
  }, [dates, selectedDate, width, innerWidth, xScale, findClosestDate, onDateChange]);

  // Playback effect
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      const currentIndex = sortedDates.findIndex(
        (d) => d.getTime() === selectedDate.getTime()
      );
      const nextIndex = (currentIndex + 1) % sortedDates.length;
      onDateChange(sortedDates[nextIndex]);
    }, 1000 / playbackSpeed);

    return () => clearInterval(interval);
  }, [isPlaying, selectedDate, sortedDates, playbackSpeed, onDateChange]);

  return (
    <div className="time-slider">
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
