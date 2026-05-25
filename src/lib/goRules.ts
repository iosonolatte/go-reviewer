/**
 * 围棋规则引擎：处理提子、气、合法落子等
 */

export type Stone = "B" | "W" | null;

export interface BoardState {
  size: number;
  /** board[y][x] */
  cells: Stone[][];
}

export interface PlayResult {
  board: BoardState;
  captured: number;
}

const LETTERS = "ABCDEFGHJKLMNOPQRST";

export function createEmptyBoard(size: number = 19): BoardState {
  return {
    size,
    cells: Array.from({ length: size }, () => Array(size).fill(null)),
  };
}

export function cloneBoard(board: BoardState): BoardState {
  return {
    size: board.size,
    cells: board.cells.map((row) => row.slice()),
  };
}

/** 把 SGF 风格的 (x,y) 转换 - 注意 SGF 的 y 与显示 y 一致 */
function neighbors(
  x: number,
  y: number,
  size: number,
): Array<[number, number]> {
  const result: Array<[number, number]> = [];
  if (x > 0) result.push([x - 1, y]);
  if (x < size - 1) result.push([x + 1, y]);
  if (y > 0) result.push([x, y - 1]);
  if (y < size - 1) result.push([x, y + 1]);
  return result;
}

/** 找到从 (x,y) 出发同色棋块的所有点和气数 */
function findGroup(
  board: BoardState,
  x: number,
  y: number,
): { stones: Array<[number, number]>; liberties: number } {
  const color = board.cells[y][x];
  if (!color) return { stones: [], liberties: 0 };

  const visited = new Set<string>();
  const libertySet = new Set<string>();
  const stones: Array<[number, number]> = [];
  const stack: Array<[number, number]> = [[x, y]];

  while (stack.length > 0) {
    const [cx, cy] = stack.pop()!;
    const key = `${cx},${cy}`;
    if (visited.has(key)) continue;
    visited.add(key);

    if (board.cells[cy][cx] !== color) continue;
    stones.push([cx, cy]);

    for (const [nx, ny] of neighbors(cx, cy, board.size)) {
      const ncolor = board.cells[ny][nx];
      const nkey = `${nx},${ny}`;
      if (ncolor === null) {
        libertySet.add(nkey);
      } else if (ncolor === color && !visited.has(nkey)) {
        stack.push([nx, ny]);
      }
    }
  }

  return { stones, liberties: libertySet.size };
}

/**
 * 在棋盘上落子，并执行提子规则
 * 返回新棋盘 + 被提子数量
 */
export function playMove(
  board: BoardState,
  x: number,
  y: number,
  color: "B" | "W",
): PlayResult {
  const newBoard = cloneBoard(board);

  if (x < 0 || x >= newBoard.size || y < 0 || y >= newBoard.size) {
    return { board: newBoard, captured: 0 };
  }
  if (newBoard.cells[y][x] !== null) {
    // 该位置已有棋子，不合法落子（这里宽松处理：直接覆盖也不太好；返回原样）
    return { board: newBoard, captured: 0 };
  }

  newBoard.cells[y][x] = color;
  const opponent: Stone = color === "B" ? "W" : "B";

  let totalCaptured = 0;

  // 1. 检查相邻的对方棋块是否有气，没气则提走
  for (const [nx, ny] of neighbors(x, y, newBoard.size)) {
    if (newBoard.cells[ny][nx] === opponent) {
      const { stones, liberties } = findGroup(newBoard, nx, ny);
      if (liberties === 0) {
        for (const [sx, sy] of stones) {
          newBoard.cells[sy][sx] = null;
        }
        totalCaptured += stones.length;
      }
    }
  }

  // 2. 自杀检查：本方棋块如果落子后还是没气，要么是非法（这里宽松处理：自提）
  const { stones: ownStones, liberties: ownLib } = findGroup(newBoard, x, y);
  if (ownLib === 0 && totalCaptured === 0) {
    for (const [sx, sy] of ownStones) {
      newBoard.cells[sy][sx] = null;
    }
  }

  return { board: newBoard, captured: totalCaptured };
}

/**
 * 重放从开始到指定手数的棋谱，得到当前局面
 * moves 来自 store: [{ color, x, y, ... }, ...]
 */
export function replayMoves(
  size: number,
  moves: Array<{ color: "B" | "W"; x: number; y: number }>,
  upTo: number,
): BoardState {
  let board = createEmptyBoard(size);
  const limit = Math.min(upTo, moves.length);
  for (let i = 0; i < limit; i++) {
    const m = moves[i];
    if (m.x >= 0 && m.x < size && m.y >= 0 && m.y < size) {
      board = playMove(board, m.x, m.y, m.color).board;
    }
  }
  return board;
}

export function kataPosToXY(
  pos: string,
  boardSize: number = 19,
): [number, number] {
  if (!pos || pos.toLowerCase() === "pass") return [-1, -1];
  const letter = pos[0].toUpperCase();
  const num = parseInt(pos.slice(1), 10);
  if (isNaN(num)) return [-1, -1];
  const x = LETTERS.indexOf(letter);
  const y = boardSize - num;
  return [x, y];
}
