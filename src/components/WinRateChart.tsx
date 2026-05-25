import React from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { Game } from "../types";

interface WinRateChartProps {
  game: Game;
  currentMove: number;
}

const WinRateChart: React.FC<WinRateChartProps> = ({ game, currentMove }) => {
  const data = Object.entries(game.analyses)
    .map(([moveNum, analysis]) => ({
      move: parseInt(moveNum),
      winRate: analysis.winRate,
      scoreLead: analysis.scoreLead,
    }))
    .sort((a, b) => a.move - b.move);

  const totalAnalyzed = data.length;
  const currentData = data.find((d) => d.move === currentMove);
  const minRate =
    data.length > 0 ? Math.min(...data.map((d) => d.winRate)) : 50;
  const maxRate =
    data.length > 0 ? Math.max(...data.map((d) => d.winRate)) : 50;

  return (
    <div className="bg-white rounded-xl shadow-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-serif text-go-wood font-medium">
          胜率曲线
        </h3>
        <div className="text-xs text-go-woodLight">
          已分析 {totalAnalyzed} 手 · 波动 {minRate.toFixed(0)}-
          {maxRate.toFixed(0)}%
        </div>
      </div>

      {currentData && (
        <div className="flex items-center justify-between mb-2 px-1 text-sm">
          <span className="text-go-woodLight">第 {currentMove} 手</span>
          <div className="flex items-center gap-3">
            <span
              className={
                currentData.winRate >= 50
                  ? "text-gray-900 font-bold"
                  : "text-gray-500"
              }
            >
              ⬛黑 {currentData.winRate.toFixed(1)}%
            </span>
            <span
              className={
                currentData.winRate < 50
                  ? "text-gray-900 font-bold"
                  : "text-gray-500"
              }
            >
              ⬜白 {(100 - currentData.winRate).toFixed(1)}%
            </span>
          </div>
        </div>
      )}

      <div className="h-44">
        {data.length === 0 ? (
          <div className="flex items-center justify-center h-full text-go-woodLight text-sm">
            尚无分析数据，请先分析棋手
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={data}
              margin={{ top: 5, right: 10, left: -10, bottom: 5 }}
            >
              <defs>
                <linearGradient id="blackArea" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#1f2937" stopOpacity={0.6} />
                  <stop offset="50%" stopColor="#374151" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#374151" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="whiteArea" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f3f4f6" stopOpacity={0} />
                  <stop offset="50%" stopColor="#9ca3af" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#6b7280" stopOpacity={0.5} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
              <XAxis
                dataKey="move"
                tick={{ fontSize: 10 }}
                stroke="#8D6E63"
                interval="preserveStartEnd"
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 10 }}
                stroke="#8D6E63"
                tickFormatter={(v) => `${v}`}
                ticks={[0, 25, 50, 75, 100]}
              />
              <Tooltip
                formatter={(value: number, _name: string, item: any) => {
                  const score = item.payload?.scoreLead;
                  return [
                    `黑 ${value.toFixed(1)}% / 白 ${(100 - value).toFixed(1)}%${
                      score !== undefined
                        ? ` (目差 ${score >= 0 ? "+" : ""}${score.toFixed(1)})`
                        : ""
                    }`,
                    "",
                  ];
                }}
                labelFormatter={(label) => `第 ${label} 手`}
                contentStyle={{
                  backgroundColor: "#FFF8E1",
                  border: "1px solid #D2B48C",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
              />
              <ReferenceLine y={50} stroke="#9ca3af" strokeDasharray="3 3" />
              {currentMove > 0 && (
                <ReferenceLine
                  x={currentMove}
                  stroke="#FF6B35"
                  strokeWidth={2}
                  strokeDasharray="0"
                  label={{
                    value: "当前",
                    position: "top",
                    fill: "#FF6B35",
                    fontSize: 10,
                  }}
                />
              )}
              <Area
                type="monotone"
                dataKey="winRate"
                stroke="#1f2937"
                strokeWidth={2}
                fill="url(#blackArea)"
                fillOpacity={1}
                dot={{ r: 2, fill: "#1f2937" }}
                activeDot={{
                  r: 5,
                  fill: "#FF6B35",
                  stroke: "#fff",
                  strokeWidth: 2,
                }}
                isAnimationActive={true}
                animationDuration={300}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="flex justify-between text-xs text-go-woodLight mt-2 px-1">
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-full bg-gray-800"></span>
          黑棋胜率（曲线越高越好）
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-full bg-gray-300 border border-gray-400"></span>
          白棋区域
        </span>
      </div>
    </div>
  );
};

export default WinRateChart;
