export interface Move {
  number: number;
  color: "B" | "W";
  position: string;
  x: number;
  y: number;
}

export interface RecommendedMove {
  position: string;
  winRate: number;
  visits: number;
}

export interface Analysis {
  moveNumber: number;
  winRate: number;
  scoreLead: number;
  recommendedMoves: RecommendedMove[];
  commentary?: string;
}

export interface Game {
  gameId: string;
  moves: Move[];
  boardSize: number;
  komi: number;
  playerBlack: string;
  playerWhite: string;
  result: string;
  analyses: { [key: number]: Analysis };
}

export interface KataGoConfig {
  path: string;
  configPath: string;
  modelPath: string;
  analyzeTime: number;
}

export interface LLMConfig {
  apiKey: string;
  model: string;
  baseUrl?: string;
}
