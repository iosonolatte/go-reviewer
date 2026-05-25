import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { Game, Analysis, KataGoConfig, LLMConfig } from "../types";

interface GameState {
  currentGame: Game | null;
  currentMove: number;
  isAnalyzing: boolean;
  isGeneratingCommentary: boolean;
  katagoConfig: KataGoConfig;
  llmConfig: LLMConfig;

  setCurrentGame: (game: Game | null) => void;
  setCurrentMove: (move: number) => void;
  setIsAnalyzing: (value: boolean) => void;
  setIsGeneratingCommentary: (value: boolean) => void;
  setKatagoConfig: (config: Partial<KataGoConfig>) => void;
  setLLMConfig: (config: Partial<LLMConfig>) => void;
  addAnalysis: (moveNumber: number, analysis: Analysis) => void;
  setCommentary: (moveNumber: number, commentary: string) => void;
  nextMove: () => void;
  prevMove: () => void;
  goToMove: (move: number) => void;
  /** 创建一个空白对局 */
  createEmptyGame: (boardSize?: number) => void;
  /** 在当前手数处追加一手新棋（用于实时落子模式） */
  appendMove: (x: number, y: number) => void;
  /** 撤销最后一手（仅当当前已是最后一手时） */
  undoLastMove: () => void;
}

export const useGameStore = create<GameState>()(
  persist(
    (set) => ({
      currentGame: null,
      currentMove: 0,
      isAnalyzing: false,
      isGeneratingCommentary: false,
      katagoConfig: {
        path: "",
        configPath: "",
        modelPath: "",
        analyzeTime: 3,
      },
      llmConfig: {
        apiKey: "",
        model: "gpt-4",
        baseUrl: undefined,
      },

      setCurrentGame: (game) =>
        set({ currentGame: game, currentMove: game ? 0 : 0 }),
      setCurrentMove: (move) => set({ currentMove: move }),
      setIsAnalyzing: (value) => set({ isAnalyzing: value }),
      setIsGeneratingCommentary: (value) =>
        set({ isGeneratingCommentary: value }),
      setKatagoConfig: (config) =>
        set((state) => ({
          katagoConfig: { ...state.katagoConfig, ...config },
        })),
      setLLMConfig: (config) =>
        set((state) => ({
          llmConfig: { ...state.llmConfig, ...config },
        })),
      addAnalysis: (moveNumber, analysis) =>
        set((state) => {
          if (!state.currentGame) return state;
          return {
            currentGame: {
              ...state.currentGame,
              analyses: {
                ...state.currentGame.analyses,
                [moveNumber]: analysis,
              },
            },
          };
        }),
      setCommentary: (moveNumber, commentary) =>
        set((state) => {
          if (!state.currentGame || !state.currentGame.analyses[moveNumber])
            return state;
          return {
            currentGame: {
              ...state.currentGame,
              analyses: {
                ...state.currentGame.analyses,
                [moveNumber]: {
                  ...state.currentGame.analyses[moveNumber],
                  commentary,
                },
              },
            },
          };
        }),
      nextMove: () =>
        set((state) => {
          if (!state.currentGame) return state;
          const maxMove = state.currentGame.moves.length;
          return {
            currentMove: Math.min(state.currentMove + 1, maxMove),
          };
        }),
      prevMove: () =>
        set((state) => ({
          currentMove: Math.max(state.currentMove - 1, 0),
        })),
      goToMove: (move) =>
        set((state) => {
          if (!state.currentGame) return state;
          const maxMove = state.currentGame.moves.length;
          return {
            currentMove: Math.max(0, Math.min(move, maxMove)),
          };
        }),

      createEmptyGame: (boardSize = 19) => {
        const gameId = `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        set({
          currentGame: {
            gameId,
            moves: [],
            boardSize,
            komi: 6.5,
            playerBlack: "黑方",
            playerWhite: "白方",
            result: "",
            analyses: {},
          },
          currentMove: 0,
        });
      },

      appendMove: (x, y) =>
        set((state) => {
          if (!state.currentGame) return state;
          const game = state.currentGame;
          // 如果当前不在最后一手，先截断后续棋子（变化分支）
          const baseMoves = game.moves.slice(0, state.currentMove);
          // 推断落子方
          const lastColor = baseMoves[baseMoves.length - 1]?.color;
          const nextColor: "B" | "W" = lastColor === "B" ? "W" : "B";
          // 转换坐标：x 是棋盘列(0-18)，y 是棋盘行(0-18，从顶部数)
          const LETTERS = "ABCDEFGHJKLMNOPQRST";
          const position = `${LETTERS[x]}${game.boardSize - y}`;
          const newMove = {
            number: baseMoves.length + 1,
            color: nextColor,
            position,
            x,
            y,
          };
          // 同时清空被截断手的分析（已无效）
          const newAnalyses: typeof game.analyses = {};
          for (const [k, v] of Object.entries(game.analyses)) {
            const n = parseInt(k);
            if (n <= state.currentMove) newAnalyses[n] = v;
          }
          return {
            currentGame: {
              ...game,
              moves: [...baseMoves, newMove],
              analyses: newAnalyses,
            },
            currentMove: state.currentMove + 1,
          };
        }),

      undoLastMove: () =>
        set((state) => {
          if (!state.currentGame || state.currentGame.moves.length === 0)
            return state;
          const game = state.currentGame;
          const lastIdx = game.moves.length;
          const newMoves = game.moves.slice(0, -1);
          const newAnalyses: typeof game.analyses = {};
          for (const [k, v] of Object.entries(game.analyses)) {
            const n = parseInt(k);
            if (n < lastIdx) newAnalyses[n] = v;
          }
          return {
            currentGame: { ...game, moves: newMoves, analyses: newAnalyses },
            currentMove: Math.min(state.currentMove, newMoves.length),
          };
        }),
    }),
    {
      name: "go-reviewer-storage",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        katagoConfig: state.katagoConfig,
        llmConfig: state.llmConfig,
      }),
    },
  ),
);
