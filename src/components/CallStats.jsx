import React, { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { ChevronDown } from "lucide-react";
import { format, parseISO } from "date-fns";
import api from "../lib/api";

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="px-4 py-3 rounded-xl shadow-premium text-sm"
      style={{ backgroundColor: "#181c1c", color: "#f7faf9" }}
    >
      <p className="font-semibold mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="text-xs" style={{ color: p.fill }}>
          {p.dataKey}: {p.value}
        </p>
      ))}
    </div>
  );
};

const CallStats = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);

  useEffect(() => {
    const fetchTimeline = async () => {
      try {
        setLoading(true);
        const res = await api.get(`/dashboard/timeline?days=${days}`);
        setData(
          res.data.data.map((item) => ({
            name: format(parseISO(item.date), "eee"),
            calls: item.calls,
            bookings: item.bookings,
          })),
        );
      } catch (err) {
        console.error("Failed to load timeline data", err);
      } finally {
        setLoading(false);
      }
    };
    fetchTimeline();
  }, [days]);

  return (
    <div className="bg-white rounded-2xl p-6 shadow-card flex flex-col h-full w-full">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h3 className="font-bold text-on-surface text-base">Call Volume</h3>
          <div className="w-6 h-0.5 bg-primary mt-1" />
        </div>

        <div className="relative">
          <select
            className="appearance-none bg-surface-container text-on-surface-variant font-medium text-sm rounded-xl pl-3 pr-8 py-2 outline-none cursor-pointer transition-colors hover:bg-surface-high"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={7}>This Week</option>
            <option value={14}>Last 14 Days</option>
            <option value={30}>This Month</option>
          </select>
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-on-surface-variant">
            <ChevronDown className="w-4 h-4" />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4 mb-4">
        <div className="flex items-center gap-1.5 text-xs text-on-surface-variant">
          <span
            className="w-3 h-3 rounded-sm"
            style={{ backgroundColor: "#7dbd42" }}
          />
          Calls
        </div>
        <div className="flex items-center gap-1.5 text-xs text-on-surface-variant">
          <span className="w-3 h-3 rounded-sm bg-rose-300" />
          Missed
        </div>
      </div>

      <div className="flex-1 min-h-[260px]">
        {loading ? (
          <div className="w-full h-full flex items-center justify-center text-on-surface-variant text-sm">
            Loading...
          </div>
        ) : data.length === 0 ? (
          <div className="w-full h-full flex items-center justify-center text-on-surface-variant text-sm">
            No data for this period
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              margin={{ top: 4, right: 4, left: -24, bottom: 0 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="#edf1ef"
              />
              <XAxis
                dataKey="name"
                axisLine={false}
                tickLine={false}
                tick={{ fill: "#3d4946", fontSize: 11 }}
                dy={8}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fill: "#3d4946", fontSize: 11 }}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={{ fill: "#edf1ef" }}
              />
              <Bar
                dataKey="calls"
                fill="#7dbd42"
                radius={[4, 4, 0, 0]}
                maxBarSize={36}
              />
              <Bar
                dataKey="bookings"
                fill="#fca5a5"
                radius={[4, 4, 0, 0]}
                maxBarSize={36}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};

export default CallStats;
