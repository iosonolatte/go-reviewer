import React, { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  SkipBack,
  SkipForward,
  ChevronLeft,
  ChevronRight,
  Brain,
  Upload,
  AlertCircle,
  Zap,
  Sparkles,
  Square,
  Eye,
  Hand,
  Undo2,
  RotateCcw,
} from "lucide-react";
import { useGameStore } from "../store/gameStore";
import GoBoard from "../components/GoBoard";
import WinRateChart from "../components/WinRateChart";
import CommentaryPanel from "../components/CommentaryPanel";
import MoveTimeline from "../components/MoveTimeline";
import HawkEyePanel, { HawkEyeData } from "../components/HawkEyePanel";

type RightTab = "analysis" | "hawkeye";

const Review: React.FC = () => {
  const navigate = useNavigate();
  const {
    currentGame,
    currentMove,
    isAnalyzing,
    isGeneratingCommentary,
    goToMove,
    nextMove,
    prevMove,
    setIsAnalyzing,
    setIsGeneratingCommentary,
    addAnalysis,
    setCommentary,
    appendMove,
    undoLastMove,
    createEmptyGame,
  } = useGameStore();

  const [autoAnalyze, setAutoAnalyze] = useState(true);
  const [autoCommentary, setAutoCommentary] = useState(false);
  const [batchAnalyzing, setBatchAnalyzing] = useState(false);
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0 });
  const [flashAnalyzing, setFlashAnalyzing] = useState(false);
  const [hawkEyeData, setHawkEyeData] = useState<HawkEyeData | null>(null);
  const [rightTab, setRightTab] = useState<RightTab>("analysis");
  const [liveMode, setLiveMode] = useState(true);
  const stopBatchRef = useRef(false);
  const inflightRef = useRef<{ [moveNum: number]: Promise<boolean> }>({});

  const analyzeMove = useCallback(
    async (moveNum: number): Promise<boolean> => {
      if (!currentGame || moveNum === 0) return false;
      if (currentGame.analyses[moveNum]) return true;

      if (inflightRef.current[moveNum]) {
        return inflightRef.current[moveNum];
      }

      const promise = (async () => {
        try {
          // 使用 AbortController 让相同 moveNum 的旧请求可被取消
          const controller = new AbortController();
          const response = await fetch(
            `http://localhost:5000/api/analyze/${currentGame.gameId}/${moveNum}`,
            { signal: controller.signal },
          );
          if (response.status === 404) {
            console.warn("棋谱在后端不存在，可能后端已重启");
            return false;
          }
          if (!response.ok) return false;
          const analysis = await response.json();
          addAnalysis(moveNum, analysis);
          return true;
        } catch (error) {
          if ((error as Error).name === "AbortError") return false;
          console.error("分析失败:", error);
          return false;
        } finally {
          delete inflightRef.current[moveNum];
        }
      })();

      inflightRef.current[moveNum] = promise;
      return promise;
    },
    [currentGame, addAnalysis],
  );

  const generateCommentary = useCallback(
    async (moveNum: number): Promise<boolean> => {
      if (!currentGame || moveNum === 0) return false;
      if (currentGame.analyses[moveNum]?.commentary) return true;

      try {
        const response = await fetch(
          `http://localhost:5000/api/commentary/${currentGame.gameId}/${moveNum}`,
        );
        if (!response.ok) return false;
        const data = await response.json();
        setCommentary(moveNum, data.commentary);
        return true;
      } catch (error) {
        console.error("生成解说失败:", error);
        return false;
      }
    },
    [currentGame, setCommentary],
  );

  const handleAnalyze = async () => {
    if (!currentGame || currentMove === 0) return;
    setIsAnalyzing(true);
    try {
      const ok = await analyzeMove(currentMove);
      if (!ok) alert("KataGo 分析失败，请检查引擎配置");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleGenerateCommentary = async () => {
    if (!currentGame || currentMove === 0) return;
    setIsGeneratingCommentary(true);
    try {
      const ok = await generateCommentary(currentMove);
      if (!ok) alert("AI 解说生成失败");
    } finally {
      setIsGeneratingCommentary(false);
    }
  };

  useEffect(() => {
    if (!autoAnalyze || !currentGame || currentMove === 0) return;
    if (currentGame.analyses[currentMove]) return;
    if (isAnalyzing || batchAnalyzing || flashAnalyzing) return;

    const timer = window.setTimeout(async () => {
      setIsAnalyzing(true);
      try {
        const ok = await analyzeMove(currentMove);
        if (ok && autoCommentary) {
          setIsGeneratingCommentary(true);
          try {
            await generateCommentary(currentMove);
          } finally {
            setIsGeneratingCommentary(false);
          }
        }
      } finally {
        setIsAnalyzing(false);
      }
    }, 300);

    return () => window.clearTimeout(timer);
  }, [
    currentMove,
    autoAnalyze,
    autoCommentary,
    currentGame,
    analyzeMove,
    generateCommentary,
    isAnalyzing,
    batchAnalyzing,
    flashAnalyzing,
    setIsAnalyzing,
    setIsGeneratingCommentary,
  ]);

  // 预测性分析：当前手分析完成后，悄悄预取相邻手（前/后）以便快速切换
  useEffect(() => {
    if (!autoAnalyze || !currentGame || currentMove === 0) return;
    if (!currentGame.analyses[currentMove]) return; // 当前手还没分析完，不预取
    if (isAnalyzing || batchAnalyzing || flashAnalyzing) return;

    const total = currentGame.moves.length;
    const targets: number[] = [];
    if (currentMove + 1 <= total && !currentGame.analyses[currentMove + 1]) {
      targets.push(currentMove + 1);
    }
    if (currentMove - 1 >= 1 && !currentGame.analyses[currentMove - 1]) {
      targets.push(currentMove - 1);
    }
    if (targets.length === 0) return;

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      for (const t of targets) {
        if (cancelled) break;
        // 静默预取，不更改 isAnalyzing 状态（避免 UI 闪烁）
        await analyzeMove(t);
      }
    }, 800);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [
    currentMove,
    autoAnalyze,
    currentGame,
    analyzeMove,
    isAnalyzing,
    batchAnalyzing,
    flashAnalyzing,
  ]);

  const handleBatchAnalyze = async () => {
    if (!currentGame) return;
    if (batchAnalyzing) {
      stopBatchRef.current = true;
      return;
    }

    setBatchAnalyzing(true);
    stopBatchRef.current = false;
    const total = currentGame.moves.length;
    setBatchProgress({ current: 0, total });

    for (let i = 1; i <= total; i++) {
      if (stopBatchRef.current) break;
      setBatchProgress({ current: i, total });
      goToMove(i);
      await analyzeMove(i);
    }

    setBatchAnalyzing(false);
    stopBatchRef.current = false;
    setBatchProgress({ current: 0, total: 0 });
  };

  const handleFlashAnalyze = async () => {
    if (!currentGame || flashAnalyzing) return;
    setFlashAnalyzing(true);
    try {
      const response = await fetch(
        `http://localhost:5000/api/flash-analyze/${currentGame.gameId}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            maxVisits: Math.max(
              100,
              Math.min(
                5000,
                (useGameStore.getState().katagoConfig.analyzeTime || 3) * 250,
              ),
            ),
          }),
        },
      );
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || "闪电分析失败");
      }
      const data = await response.json();
      Object.entries(data.analyses).forEach(
        ([num, analysis]: [string, any]) => {
          addAnalysis(parseInt(num), analysis);
        },
      );
      await loadHawkEye();
      setRightTab("hawkeye");
    } catch (error) {
      console.error(error);
      alert(`闪电分析失败：${(error as Error).message}`);
    } finally {
      setFlashAnalyzing(false);
    }
  };

  const loadHawkEye = useCallback(async () => {
    if (!currentGame) return;
    try {
      const response = await fetch(
        `http://localhost:5000/api/hawk-eye/${currentGame.gameId}`,
      );
      if (!response.ok) return;
      const data = await response.json();
      setHawkEyeData(data);
    } catch (error) {
      console.error("鹰眼分析失败:", error);
    }
  }, [currentGame]);

  // 实时落子：用户点击棋盘时调用
  const handlePlayMove = useCallback(
    (x: number, y: number) => {
      if (!currentGame) return;
      // 1. 本地立刻落子（乐观更新，让 UI 即时响应）
      appendMove(x, y);

      // 2. 推断颜色和坐标
      const lastColor = currentGame.moves[currentMove - 1]?.color;
      const nextColor: "B" | "W" = lastColor === "B" ? "W" : "B";
      const LETTERS = "ABCDEFGHJKLMNOPQRST";
      const position = `${LETTERS[x]}${currentGame.boardSize - y}`;

      // 3. 异步同步到后端（如果是远程对局）
      if (!currentGame.gameId.startsWith("local-")) {
        fetch(`http://localhost:5000/api/game/${currentGame.gameId}/play`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ color: nextColor, position }),
        }).catch((err) => console.warn("同步到后端失败:", err));
      }
    },
    [currentGame, currentMove, appendMove],
  );

  // 悔棋
  const handleUndo = useCallback(() => {
    if (!currentGame || currentGame.moves.length === 0) return;
    undoLastMove();
    if (!currentGame.gameId.startsWith("local-")) {
      fetch(`http://localhost:5000/api/game/${currentGame.gameId}/undo`, {
        method: "POST",
      }).catch((err) => console.warn("同步悔棋失败:", err));
    }
  }, [currentGame, undoLastMove]);

  // 重新开局（清空所有手）
  const handleResetGame = useCallback(async () => {
    if (!confirm("确定要清空当前棋盘重新开始吗？")) return;
    try {
      const response = await fetch("http://localhost:5000/api/game/new", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ boardSize: 19, komi: 6.5 }),
      });
      if (response.ok) {
        const data = await response.json();
        useGameStore.getState().setCurrentGame({
          gameId: data.gameId,
          moves: [],
          boardSize: data.boardSize || 19,
          komi: data.komi || 6.5,
          playerBlack: "黑方",
          playerWhite: "白方",
          result: "",
          analyses: {},
        });
      } else {
        createEmptyGame(19);
      }
    } catch {
      createEmptyGame(19);
    }
  }, [createEmptyGame]);

  if (!currentGame) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-amber-50 via-orange-50 to-yellow-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-go-wood mb-4">请先上传棋谱文件</p>
          <button
            onClick={() => navigate("/")}
            className="px-6 py-2 bg-go-wood text-white rounded-lg hover:bg-go-woodLight transition-colors"
          >
            返回首页
          </button>
        </div>
      </div>
    );
  }

  const currentAnalysis = currentGame.analyses[currentMove];
  const hasAnalysis = !!currentAnalysis;
  const totalAnalyzed = Object.keys(currentGame.analyses).length;

  return (
    <div className="min-h-screen bg-gradient-to-br from-amber-50 via-orange-50 to-yellow-50">
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="bg-white rounded-xl shadow-lg p-4 mb-6">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-xl font-serif font-bold text-go-wood">
                {currentGame.playerBlack || "黑方"} vs{" "}
                {currentGame.playerWhite || "白方"}
              </h1>
              {currentGame.result && (
                <p className="text-sm text-go-woodLight">
                  结果：{currentGame.result}
                </p>
              )}
              <p className="text-xs text-go-woodLight mt-1">
                已分析 {totalAnalyzed} / {currentGame.moves.length} 手
              </p>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <label className="flex items-center gap-1 text-sm text-go-wood cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={autoAnalyze}
                  onChange={(e) => setAutoAnalyze(e.target.checked)}
                  className="accent-go-accent"
                />
                自动分析
              </label>
              <label className="flex items-center gap-1 text-sm text-go-wood cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={autoCommentary}
                  onChange={(e) => setAutoCommentary(e.target.checked)}
                  className="accent-go-accent"
                />
                自动解说
              </label>
              <label
                className={`flex items-center gap-1 text-sm cursor-pointer select-none px-2 py-1 rounded-lg ${liveMode ? "bg-emerald-500 text-white" : "text-go-wood hover:bg-emerald-50"}`}
              >
                <input
                  type="checkbox"
                  checked={liveMode}
                  onChange={(e) => setLiveMode(e.target.checked)}
                  className="hidden"
                />
                <Hand className="w-4 h-4" />
                落子模式
              </label>
              {liveMode && currentGame.moves.length > 0 && (
                <button
                  onClick={handleUndo}
                  className="px-3 py-1.5 bg-amber-100 text-amber-800 rounded-lg hover:bg-amber-200 transition-colors flex items-center gap-1 text-sm"
                  title="悔棋"
                >
                  <Undo2 className="w-4 h-4" />
                  悔棋
                </button>
              )}
              {liveMode && currentGame.moves.length > 0 && (
                <button
                  onClick={handleResetGame}
                  className="px-3 py-1.5 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition-colors flex items-center gap-1 text-sm"
                  title="清空棋盘重新开始"
                >
                  <RotateCcw className="w-4 h-4" />
                  重置
                </button>
              )}
              <button
                onClick={() => navigate("/")}
                className="px-3 py-1.5 bg-go-board text-go-wood rounded-lg hover:bg-go-boardDark transition-colors flex items-center gap-2 text-sm"
              >
                <Upload className="w-4 h-4" />
                上传棋谱
              </button>
            </div>
          </div>

          {batchAnalyzing && (
            <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <div className="flex items-center justify-between text-sm">
                <span className="text-amber-800">
                  批量分析中：{batchProgress.current} / {batchProgress.total}
                </span>
                <button
                  onClick={() => {
                    stopBatchRef.current = true;
                  }}
                  className="px-2 py-1 bg-red-500 text-white rounded text-xs hover:bg-red-600"
                >
                  停止
                </button>
              </div>
              <div className="mt-2 h-2 bg-amber-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-go-accent transition-all duration-300"
                  style={{
                    width: `${(batchProgress.current / batchProgress.total) * 100}%`,
                  }}
                />
              </div>
            </div>
          )}

          {flashAnalyzing && (
            <div className="mt-3 p-3 bg-indigo-50 border border-indigo-200 rounded-lg">
              <div className="flex items-center gap-2 text-sm text-indigo-800">
                <Zap className="w-4 h-4 animate-pulse" />
                <span>闪电分析中... KataGo 正在并行分析整局棋谱</span>
              </div>
            </div>
          )}
        </div>

        <div className="grid lg:grid-cols-5 gap-6">
          <div className="lg:col-span-3">
            <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
              <div className="flex justify-center mb-6">
                <GoBoard
                  boardSize={currentGame.boardSize}
                  moves={currentGame.moves}
                  currentMove={currentMove}
                  recommendedMoves={currentAnalysis?.recommendedMoves}
                  onMoveClick={goToMove}
                  interactive={liveMode}
                  onPlayMove={liveMode ? handlePlayMove : undefined}
                />
              </div>

              <div className="flex items-center justify-center gap-3 mb-4 flex-wrap">
                <button
                  onClick={() => goToMove(0)}
                  className="p-2 rounded-lg bg-go-board text-go-wood hover:bg-go-boardDark transition-colors disabled:opacity-50"
                  disabled={currentMove === 0}
                  title="跳到开始"
                >
                  <SkipBack className="w-5 h-5" />
                </button>
                <button
                  onClick={prevMove}
                  className="p-2 rounded-lg bg-go-board text-go-wood hover:bg-go-boardDark transition-colors disabled:opacity-50"
                  disabled={currentMove === 0}
                  title="上一手"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <div className="w-24 text-center">
                  <span className="text-2xl font-bold text-go-wood">
                    {currentMove}
                  </span>
                  <span className="text-go-woodLight">
                    {" "}
                    / {currentGame.moves.length}
                  </span>
                </div>
                <button
                  onClick={nextMove}
                  className="p-2 rounded-lg bg-go-board text-go-wood hover:bg-go-boardDark transition-colors disabled:opacity-50"
                  disabled={currentMove >= currentGame.moves.length}
                  title="下一手"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
                <button
                  onClick={() => goToMove(currentGame.moves.length)}
                  className="p-2 rounded-lg bg-go-board text-go-wood hover:bg-go-boardDark transition-colors disabled:opacity-50"
                  disabled={currentMove >= currentGame.moves.length}
                  title="跳到结尾"
                >
                  <SkipForward className="w-5 h-5" />
                </button>
              </div>

              <div className="flex items-center justify-center gap-3 flex-wrap">
                <button
                  onClick={handleAnalyze}
                  disabled={
                    isAnalyzing ||
                    currentMove === 0 ||
                    batchAnalyzing ||
                    flashAnalyzing
                  }
                  className="px-4 py-2 bg-gradient-to-r from-go-wood to-go-woodLight text-white rounded-lg hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 font-medium text-sm"
                >
                  <Brain
                    className={`w-4 h-4 ${isAnalyzing ? "animate-spin" : ""}`}
                  />
                  {isAnalyzing ? "分析中..." : "分析当前手"}
                </button>
                <button
                  onClick={handleGenerateCommentary}
                  disabled={
                    isGeneratingCommentary || !hasAnalysis || currentMove === 0
                  }
                  className="px-4 py-2 bg-gradient-to-r from-go-accent to-orange-500 text-white rounded-lg hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 font-medium text-sm"
                >
                  <Sparkles
                    className={`w-4 h-4 ${isGeneratingCommentary ? "animate-bounce" : ""}`}
                  />
                  {isGeneratingCommentary ? "解说中..." : "AI 解说"}
                </button>
                <button
                  onClick={handleFlashAnalyze}
                  disabled={isAnalyzing || flashAnalyzing || batchAnalyzing}
                  className="px-4 py-2 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 font-medium text-sm"
                  title="使用 Analysis Engine 一次性分析全局所有手"
                >
                  <Zap
                    className={`w-4 h-4 ${flashAnalyzing ? "animate-pulse" : ""}`}
                  />
                  {flashAnalyzing ? "闪电中..." : "闪电分析"}
                </button>
                <button
                  onClick={handleBatchAnalyze}
                  disabled={isAnalyzing || flashAnalyzing}
                  className={`px-4 py-2 rounded-lg transition-all flex items-center gap-2 font-medium text-sm ${
                    batchAnalyzing
                      ? "bg-red-500 text-white hover:bg-red-600"
                      : "bg-gradient-to-r from-amber-500 to-amber-600 text-white hover:shadow-lg disabled:opacity-50"
                  }`}
                  title="逐手 GTP 分析"
                >
                  {batchAnalyzing ? (
                    <>
                      <Square className="w-4 h-4" />
                      停止批量
                    </>
                  ) : (
                    <>
                      <Brain className="w-4 h-4" />
                      逐手批量
                    </>
                  )}
                </button>
              </div>
            </div>

            <MoveTimeline
              moves={currentGame.moves}
              currentMove={currentMove}
              onMoveClick={goToMove}
            />
          </div>

          <div className="lg:col-span-2 space-y-6">
            {/* Tab 切换 */}
            <div className="bg-white rounded-xl shadow-lg p-1 flex">
              <button
                onClick={() => setRightTab("analysis")}
                className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-1 ${
                  rightTab === "analysis"
                    ? "bg-gradient-to-r from-go-wood to-go-woodLight text-white shadow"
                    : "text-go-woodLight hover:bg-amber-50"
                }`}
              >
                <Brain className="w-4 h-4" />
                AI 解说
              </button>
              <button
                onClick={() => {
                  setRightTab("hawkeye");
                  if (!hawkEyeData) loadHawkEye();
                }}
                className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-1 ${
                  rightTab === "hawkeye"
                    ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow"
                    : "text-go-woodLight hover:bg-amber-50"
                }`}
              >
                <Eye className="w-4 h-4" />
                鹰眼分析
              </button>
            </div>

            {rightTab === "analysis" ? (
              <>
                {!hasAnalysis && currentMove > 0 && !autoAnalyze && (
                  <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                    <p className="text-amber-800 text-sm">
                      当前手尚未分析。开启「自动分析」后，每切换一手都会自动分析。
                    </p>
                  </div>
                )}

                <CommentaryPanel
                  analysis={currentAnalysis || null}
                  moveNumber={currentMove}
                  onPrevMove={prevMove}
                  onNextMove={nextMove}
                />

                {Object.keys(currentGame.analyses).length > 0 && (
                  <WinRateChart game={currentGame} currentMove={currentMove} />
                )}
              </>
            ) : (
              <HawkEyePanel
                data={hawkEyeData}
                currentMove={currentMove}
                onMoveClick={goToMove}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Review;
