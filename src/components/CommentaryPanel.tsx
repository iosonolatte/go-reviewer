import React, { useEffect, useState } from "react";
import { Brain, Sparkles, ChevronRight, ChevronLeft } from "lucide-react";
import { useGameStore } from "../store/gameStore";
import { Analysis } from "../types";

interface CommentaryPanelProps {
  analysis: Analysis | null;
  moveNumber: number;
  onPrevMove: () => void;
  onNextMove: () => void;
}

const CommentaryPanel: React.FC<CommentaryPanelProps> = ({
  analysis,
  moveNumber,
  onPrevMove,
  onNextMove,
}) => {
  const { isGeneratingCommentary, currentGame } = useGameStore();
  const [displayCommentary, setDisplayCommentary] = useState("");

  useEffect(() => {
    if (analysis?.commentary) {
      setDisplayCommentary(analysis.commentary);
    } else {
      setDisplayCommentary("");
    }
  }, [analysis]);

  const currentMove = currentGame?.moves[moveNumber - 1];

  // 推断下一手轮到谁：上一手是黑则下一手是白
  const sideToMove: "B" | "W" = !currentMove
    ? "B"
    : currentMove.color === "B"
      ? "W"
      : "B";
  const sideToMoveLabel = sideToMove === "B" ? "黑棋" : "白棋";
  const sideOpponentLabel = sideToMove === "B" ? "白棋" : "黑棋";

  // KataGo 分析中的 winRate 默认是黑棋胜率，按当前轮次转换
  const sideWinRate =
    analysis && analysis.winRate !== null && analysis.winRate !== undefined
      ? sideToMove === "B"
        ? analysis.winRate
        : 100 - analysis.winRate
      : null;

  return (
    <div className="bg-gradient-to-br from-amber-50 to-orange-50 rounded-xl shadow-lg overflow-hidden">
      <div className="bg-gradient-to-r from-go-wood to-go-woodLight p-4 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5" />
            <h3 className="text-lg font-serif font-medium">AI 智能解说</h3>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onPrevMove}
              className="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
              disabled={moveNumber <= 1}
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="font-medium min-w-[60px] text-center">
              第 {moveNumber} 手
            </span>
            <button
              onClick={onNextMove}
              className="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
              disabled={!currentGame || moveNumber >= currentGame.moves.length}
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {analysis && (analysis as any).isMock && (
          <div className="p-3 bg-amber-50 border border-amber-300 rounded-lg text-amber-800 text-xs">
            ⚠️ 当前显示的是模拟数据。请前往「设置」页配置 KataGo
            引擎以获取真实分析。
            {(analysis as any).mockReasons &&
              (analysis as any).mockReasons.length > 0 && (
                <div className="mt-1 text-amber-700">
                  原因：{(analysis as any).mockReasons.join("；")}
                </div>
              )}
          </div>
        )}

        {analysis && !(analysis as any).isMock && (
          <div className="p-2 bg-green-50 border border-green-200 rounded-lg text-green-800 text-xs flex items-center justify-between">
            <span>✅ KataGo 真实分析</span>
            {analysis.recommendedMoves?.[0] && (
              <span>
                顶层推荐 visits: {analysis.recommendedMoves[0].visits}
              </span>
            )}
          </div>
        )}

        {currentMove && (
          <div className="flex items-center gap-3 p-3 bg-white rounded-lg shadow-sm">
            <div
              className={`w-8 h-8 rounded-full shadow-stone ${currentMove.color === "B" ? "bg-go-black" : "bg-go-white border border-gray-300"}`}
            />
            <div>
              <div className="text-sm text-go-woodLight">
                {currentMove.color === "B" ? "黑棋" : "白棋"} 落子
              </div>
              <div className="font-medium text-go-wood">
                {currentMove.position}
              </div>
            </div>
          </div>
        )}

        {analysis && (
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 bg-white rounded-lg shadow-sm">
              <div className="text-xs text-go-woodLight mb-1 flex items-center justify-between">
                <span>下一手胜率</span>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded ${
                    sideToMove === "B"
                      ? "bg-gray-900 text-white"
                      : "bg-gray-100 text-gray-800 border border-gray-300"
                  }`}
                >
                  轮到{sideToMoveLabel}
                </span>
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-2xl font-bold text-go-wood">
                  {sideWinRate !== null ? sideWinRate.toFixed(1) : "--"}
                </span>
                <span className="text-sm text-go-woodLight">%</span>
              </div>
              <div className="text-[10px] text-go-woodLight mt-1">
                对手{sideOpponentLabel}：
                {sideWinRate !== null ? (100 - sideWinRate).toFixed(1) : "--"}%
              </div>
            </div>
            <div className="p-3 bg-white rounded-lg shadow-sm text-center">
              <div className="text-xs text-go-woodLight mb-1">
                目差（{sideToMoveLabel}视角）
              </div>
              <div className="text-xl font-bold text-go-wood">
                {analysis.scoreLead !== null && analysis.scoreLead !== undefined
                  ? (() => {
                      const score =
                        sideToMove === "B"
                          ? analysis.scoreLead
                          : -analysis.scoreLead;
                      return (score > 0 ? "+" : "") + score.toFixed(1);
                    })()
                  : "--"}
              </div>
              <div className="text-[10px] text-go-woodLight mt-1">
                正数=领先，负数=落后
              </div>
            </div>
          </div>
        )}

        {analysis?.recommendedMoves && analysis.recommendedMoves.length > 0 && (
          <div className="p-3 bg-white rounded-lg shadow-sm">
            <div className="text-sm text-go-woodLight mb-2 flex items-center gap-1">
              <Sparkles className="w-4 h-4 text-yellow-500" />
              {sideToMoveLabel}推荐走法
            </div>
            <div className="space-y-2">
              {analysis.recommendedMoves.slice(0, 3).map((move, idx) => {
                const wr =
                  sideToMove === "B" ? move.winRate : 100 - move.winRate;
                return (
                  <div
                    key={idx}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="font-medium text-go-wood">
                      {idx + 1}. {move.position}
                    </span>
                    <span className="text-go-woodLight">
                      胜率 {wr.toFixed(1)}%
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="p-4 bg-white rounded-lg shadow-sm min-h-[120px]">
          {isGeneratingCommentary ? (
            <div className="flex items-center justify-center h-full">
              <div className="animate-pulse flex items-center gap-2 text-go-woodLight">
                <Brain className="w-5 h-5 animate-bounce" />
                <span>AI 正在思考解说...</span>
              </div>
            </div>
          ) : displayCommentary ? (
            <div className="text-go-wood leading-relaxed whitespace-pre-line">
              {displayCommentary}
            </div>
          ) : (
            <div className="text-go-woodLight text-center py-4">
              点击"生成解说"按钮获取 AI 智能讲解
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CommentaryPanel;
