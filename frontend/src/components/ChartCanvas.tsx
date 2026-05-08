import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import type { EChartsOption } from 'echarts';

interface ChartCanvasProps {
  option: EChartsOption;
  className?: string;
}

export function ChartCanvas({ option, className }: ChartCanvasProps) {
  const chartRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!chartRef.current) return undefined;

    const chart = echarts.init(chartRef.current, undefined, { renderer: 'canvas' });
    chart.setOption(option, true);

    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(chartRef.current);

    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [option]);

  return <div ref={chartRef} className={className || 'chart-canvas'} />;
}
