import React from "react";
import {
  Eye,
  Target,
  AlertTriangle,
  AlertCircle,
  XCircle,
  CheckCircle,
} from "lucide-react";

interface HawkMove {
  moveNumber: number;
  color: "B" | "W";
  position: string;
  winRate: number | null;
  scoreLead: number | null;
  winRateChange: number | null;
  scoreChange: number | null;
  matchedRank: number;
  isMatch: boolean;
  errorLevel:
    | "excellent"
    | "good"
    | "normal"
    | "inaccuracy"
    | "mistake"
    | "blunder";
  loss: number;
}

interface HawkEyeData {
  moves: HawkMove[];
  summary: {
    blackBlunders: number;
    whiteBlunders: number;
    blackMistakes: number;
    whiteMistakes: number;
    blackInaccuracies: number;
    whiteInaccuracies: number;
    blackAccuracy: number;
    whiteAccuracy: number;
    blackMatchRate: number;
    whiteMatchRate: number;
  };
  totalMoves: number;
  analyzedMoves: number;
}

interface HawkEyePanelProps {
  data: HawkEyeData | null;
  currentMove: number;
  onMoveClick: (moveNumber: number) => void;
}

const ERROR_COLORS: Record<string, string> = {
  excellent: "bg-emerald-500",
  good: "bg-green-400",
  normal: "bg-gray-300",
  inaccuracy: "bg-yellow-400",
  mistake: "bg-orange-500",
  blunder: "bg-red-600",
};

const ERROR_LABELS: Record<string, string> = {
  excellent: "神之一手",
  good: "好棋",
  normal: "正常",
  inaccuracy: "小失误",
  mistake: "失误",
  blunder: "恶手",
};

const HawkEyePanel: React.FC<HawkEyePanelProps> = ({
  data,
  currentMove,
  onMoveClick,
}) => {
  if (!data) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6 text-center">
        <Eye className="w-12 h-12 text-go-woodLight mx-auto mb-2" />
        <p className="text-go-woodLight text-sm">
          先完成「闪电分析」后查看鹰眼报告
        </p>
      </div>
    );
  }

  const { moves, summary } = data;

  return (
    <div className="bg-white rounded-xl shadow-lg overflow-hidden">
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 p-4 text-white">
        <div className="flex items-center gap-2">
          <Eye className="w-5 h-5" />
          <h3 className="text-lg font-serif font-medium">鹰眼分析</h3>
          <span className="ml-auto text-xs opacity-80">
            已分析 {data.analyzedMoves}/{data.totalMoves}
          </span>
        </div>
      </div>

      <div className="p-4 space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 bg-gray-900 text-white rounded-lg">
            <div className="text-xs opacity-70 mb-1">⬛ 黑棋</div>
            <div className="flex items-baseline gap-1 mb-2">
              <span className="text-2xl font-bold">
                {summary.blackAccuracy.toFixed(0)}
              </span>
              <span className="text-xs opacity-60">分准确度</span>
            </div>
            <div className="text-xs space-y-0.5 opacity-90">
              <div className="flex justify-between">
                <span>吻合率</span>
                <span>{summary.blackMatchRate}%</span>
              </div>
              <div className="flex justify-between">
                <span>小失误</span>
                <span>{summary.blackInaccuracies}</span>
              </div>
              <div className="flex justify-between">
                <span>失误</span>
                <span>{summary.blackMistakes}</span>
              </div>
              <div className="flex justify-between text-red-300">
                <span>恶手</span>
                <span>{summary.blackBlunders}</span>
              </div>
            </div>
          </div>
          <div className="p-3 bg-gray-100 text-go-wood rounded-lg border border-gray-300">
            <div className="text-xs opacity-70 mb-1">⬜ 白棋</div>
            <div className="flex items-baseline gap-1 mb-2">
              <span className="text-2xl font-bold">
                {summary.whiteAccuracy.toFixed(0)}
              </span>
              <span className="text-xs opacity-60">分准确度</span>
            </div>
            <div className="text-xs space-y-0.5 opacity-90">
              <div className="flex justify-between">
                <span>吻合率</span>
                <span>{summary.whiteMatchRate}%</span>
              </div>
              <div className="flex justify-between">
                <span>小失误</span>
                <span>{summary.whiteInaccuracies}</span>
              </div>
              <div className="flex justify-between">
                <span>失误</span>
                <span>{summary.whiteMistakes}</span>
              </div>
              <div className="flex justify-between text-red-600">
                <span>恶手</span>
                <span>{summary.whiteBlunders}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="text-xs text-go-woodLight flex items-center gap-3 flex-wrap">
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-3 rounded bg-emerald-500" />
            神之一手
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-3 rounded bg-green-400" />
            好棋
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-3 rounded bg-yellow-400" />
            小失误
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-3 rounded bg-orange-500" />
            失误
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-3 rounded bg-red-600" />
            恶手
          </span>
        </div>

        <div>
          <div className="text-sm text-go-wood font-medium mb-2 flex items-center gap-1">
            <Target className="w-4 h-4" />
            每手质量分布
          </div>
          <div className="flex flex-wrap gap-1 max-h-40 overflow-y-auto p-1 bg-gray-50 rounded-lg">
            {moves.map((m) => {
              const color = ERROR_COLORS[m.errorLevel] || "bg-gray-300";
              const isCurrent = m.moveNumber === currentMove;
              return (
                <button
                  key={m.moveNumber}
                  onClick={() => onMoveClick(m.moveNumber)}
                  className={`relative w-7 h-7 rounded text-[10px] font-medium ${color} ${
                    m.color === "B" ? "text-white" : "text-gray-800"
                  } hover:scale-110 transition-transform ${
                    isCurrent ? "ring-2 ring-go-accent ring-offset-1" : ""
                  }`}
                  title={`第${m.moveNumber}手 ${m.color}${m.position} - ${ERROR_LABELS[m.errorLevel]}${
                    m.loss !== null ? ` (损失${m.loss.toFixed(1)}%)` : ""
                  }`}
                >
                  {m.moveNumber}
                </button>
              );
            })}
          </div>
        </div>

        {/* 关键失误手列表 */}
        {moves.filter(
          (m) => m.errorLevel === "mistake" || m.errorLevel === "blunder",
        ).length > 0 && (
          <div>
            <div className="text-sm text-go-wood font-medium mb-2 flex items-center gap-1">
              <AlertTriangle className="w-4 h-4 text-red-500" />
              关键失误手
            </div>
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {moves
                .filter(
                  (m) =>
                    m.errorLevel === "mistake" || m.errorLevel === "blunder",
                )
                .map((m) => {
                  const Icon =
                    m.errorLevel === "blunder" ? XCircle : AlertCircle;
                  const colorCls =
                    m.errorLevel === "blunder"
                      ? "text-red-600"
                      : "text-orange-500";
                  return (
                    <button
                      key={m.moveNumber}
                      onClick={() => onMoveClick(m.moveNumber)}
                      className="w-full flex items-center gap-2 p-2 rounded-lg hover:bg-amber-50 transition-colors text-left"
                    >
                      <Icon className={`w-4 h-4 flex-shrink-0 ${colorCls}`} />
                      <div className="flex-1 min-w-0 text-xs">
                        <span className="font-medium">
                          第 {m.moveNumber} 手
                        </span>
                        <span className="ml-1 text-go-woodLight">
                          {m.color === "B" ? "⬛黑" : "⬜白"} {m.position}
                        </span>
                        <span className={`ml-2 ${colorCls}`}>
                          损失 {m.loss.toFixed(1)}%
                        </span>
                      </div>
                    </button>
                  );
                })}
            </div>
          </div>
        )}

        {moves.filter((m) => m.errorLevel === "excellent").length > 0 && (
          <div>
            <div className="text-sm text-go-wood font-medium mb-2 flex items-center gap-1">
              <CheckCircle className="w-4 h-4 text-emerald-500" />
              妙手
            </div>
            <div className="space-y-1.5 max-h-32 overflow-y-auto">
              {moves
                .filter((m) => m.errorLevel === "excellent")
                .map((m) => (
                  <button
                    key={m.moveNumber}
                    onClick={() => onMoveClick(m.moveNumber)}
                    className="w-full flex items-center gap-2 p-2 rounded-lg hover:bg-emerald-50 transition-colors text-left"
                  >
                    <CheckCircle className="w-4 h-4 flex-shrink-0 text-emerald-500" />
                    <div className="flex-1 text-xs">
                      <span className="font-medium">第 {m.moveNumber} 手</span>
                      <span className="ml-1 text-go-woodLight">
                        {m.color === "B" ? "⬛黑" : "⬜白"} {m.position}
                      </span>
                      <span className="ml-2 text-emerald-600">
                        提升 {(-m.loss).toFixed(1)}%
                      </span>
                    </div>
                  </button>
                ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default HawkEyePanel;
export type { HawkEyeData, HawkMove };
