'use client';

import { useState, useEffect } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { getAvailability } from '@/lib/api';

interface DataPoint {
  timestamp: string;
  value: number;
  time: string;
}

function formatXAxis(ts: string): string {
  const d = new Date(ts);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:00`;
}

function formatTooltip(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleString();
}

export default function AvailabilityGraph() {
  const [data, setData] = useState<DataPoint[]>([]);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAvailability(3)
      .then((points) => {
        setData(points.map((p) => ({ ...p, time: formatXAxis(p.timestamp) })));
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="bg-white dark:bg-[#1a1a1a] rounded-xl p-6 shadow-sm">
        <h2 className="text-lg font-semibold mb-4">Service Availability (3 days)</h2>
        <div className="h-48 flex items-center justify-center text-gray-400">
          Loading availability data...
        </div>
      </div>
    );
  }

  if (error || data.length === 0) {
    return (
      <div className="bg-white dark:bg-[#1a1a1a] rounded-xl p-6 shadow-sm">
        <h2 className="text-lg font-semibold mb-4">Service Availability (3 days)</h2>
        <div className="h-48 flex items-center justify-center text-gray-400">
          Availability data unavailable
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-[#1a1a1a] rounded-xl p-6 shadow-sm">
      <h2 className="text-lg font-semibold mb-4">Service Availability (3 days)</h2>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <defs>
            <linearGradient id="availGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#667eea" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#667eea" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" opacity={0.3} />
          <XAxis
            dataKey="time"
            tick={{ fontSize: 11, fill: '#888' }}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fontSize: 11, fill: '#888' }}
            tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
            width={45}
          />
          <Tooltip
            labelFormatter={(label: any) => {
              const point = data.find((d) => d.time === String(label));
              return point ? formatTooltip(point.timestamp) : String(label);
            }}
            formatter={(value: any) => [`${Math.round(Number(value) * 100)}%`, 'Availability']}
            contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333', borderRadius: '8px', color: '#fff' }}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke="#667eea"
            strokeWidth={2}
            fill="url(#availGrad)"
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
