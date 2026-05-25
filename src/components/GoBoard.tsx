import React, { useMemo } from 'react';
import { Move, RecommendedMove } from '../types';
import { replayMoves } from '../lib/goRules';

interface GoBoardProps {
  boardSize?: number;
  moves: Move[];
  currentMove: number;
  recommendedMoves?: RecommendedMove[];
  onMoveClick?: (moveNumber: number) => void;
  /** 推荐手是给哪一方的（即下一手轮到谁）。默认根据棋谱推断 */
  nextToPlay?: 'B' | 'W';
  /** 当用户点击空位时触发，用于落子模式 */
  onPlayMove?: (x: number, y: number) => void;
  /** 是否显示坐标提示（hover 高亮） */
  interactive?: boolean;
}

const BOARD_SIZE = 19;
const CELL_SIZE = 28;
const PADDING = 20;
const STONE_SIZE = 24;

const GoBoard: React.FC<GoBoardProps> = ({
  boardSize = BOARD_SIZE,
  moves,
  currentMove,
  recommendedMoves = [],
  onMoveClick,
  nextToPlay,
  onPlayMove,
  interactive = false
}) => {
  const size = (boardSize - 1) * CELL_SIZE + PADDING * 2;
  const [hoverPos, setHoverPos] = React.useState<{ x: number; y: number } | null>(null);

  // 根据当前手数推断下一手由谁下：上一手是 B 则下一手是 W；没有上一手则默认 B 先行
  const sideToMove: 'B' | 'W' = useMemo(() => {
    if (nextToPlay) return nextToPlay;
    if (currentMove === 0) return 'B';
    const last = moves[currentMove - 1];
    return last && last.color === 'B' ? 'W' : 'B';
  }, [nextToPlay, currentMove, moves]);

  // 使用围棋规则引擎重放棋谱，得到当前局面（包含提子）
  const boardState = useMemo(() => {
    return replayMoves(boardSize, moves, currentMove);
  }, [boardSize, moves, currentMove]);

  // 根据棋盘上仍存在的棋子定位最后一手
  const lastMoveInfo = useMemo(() => {
    if (currentMove === 0) return null;
    const last = moves[currentMove - 1];
    if (!last) return null;
    // 检查最后一手是否还在棋盘上（有可能立即被反提）
    if (
      last.x >= 0 && last.x < boardSize &&
      last.y >= 0 && last.y < boardSize &&
      boardState.cells[last.y][last.x] === last.color
    ) {
      return { x: last.x, y: last.y, color: last.color, number: currentMove };
    }
    return null;
  }, [boardState, moves, currentMove, boardSize]);

  const starPoints = useMemo(() => {
    if (boardSize === 19) {
      return [
        [3, 3], [3, 9], [3, 15],
        [9, 3], [9, 9], [9, 15],
        [15, 3], [15, 9], [15, 15]
      ];
    }
    if (boardSize === 13) {
      return [[3, 3], [3, 9], [6, 6], [9, 3], [9, 9]];
    }
    return [];
  }, [boardSize]);

  const posToCoord = (x: number, y: number) => ({
    cx: PADDING + x * CELL_SIZE,
    cy: PADDING + y * CELL_SIZE
  });

  // 收集棋盘上所有还存在的棋子
  const stonesOnBoard: Array<{ x: number; y: number; color: 'B' | 'W' }> = [];
  for (let y = 0; y < boardState.size; y++) {
    for (let x = 0; x < boardState.size; x++) {
      const c = boardState.cells[y][x];
      if (c) {
        stonesOnBoard.push({ x, y, color: c });
      }
    }
  }

  // 棋子光标：根据当前轮次方生成自定义 SVG cursor（已弃用，改为 cursor:none + SVG 内幽灵棋子预览）

  return (
    <div className="relative inline-block">
      <svg
        width={size}
        height={size}
        className="rounded-lg shadow-2xl"
        style={{
          background: 'linear-gradient(135deg, #D2B48C 0%, #C4A574 50%, #B8956A 100%)',
          cursor: interactive && onPlayMove ? 'none' : 'default'
        }}
        onMouseMove={(e) => {
          if (!interactive || !onPlayMove) return;
          const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          const px = e.clientX - rect.left;
          const py = e.clientY - rect.top;
          const x = Math.round((px - PADDING) / CELL_SIZE);
          const y = Math.round((py - PADDING) / CELL_SIZE);
          if (x >= 0 && x < boardSize && y >= 0 && y < boardSize) {
            setHoverPos({ x, y });
          } else {
            setHoverPos(null);
          }
        }}
        onMouseLeave={() => setHoverPos(null)}
        onClick={(e) => {
          if (!interactive || !onPlayMove) return;
          const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          const px = e.clientX - rect.left;
          const py = e.clientY - rect.top;
          const x = Math.round((px - PADDING) / CELL_SIZE);
          const y = Math.round((py - PADDING) / CELL_SIZE);
          if (x >= 0 && x < boardSize && y >= 0 && y < boardSize) {
            // 检查该位置是否已有棋子
            if (boardState.cells[y][x] === null) {
              onPlayMove(x, y);
            }
          }
        }}
      >
        <defs>
          <radialGradient id="stone-black" cx="35%" cy="35%">
            <stop offset="0%" stopColor="#4a4a4a" />
            <stop offset="100%" stopColor="#1a1a1a" />
          </radialGradient>
          <radialGradient id="stone-white" cx="35%" cy="35%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="100%" stopColor="#d0d0d0" />
          </radialGradient>
        </defs>

        {Array.from({ length: boardSize }).map((_, i) => (
          <React.Fragment key={`line-${i}`}>
            <line
              x1={PADDING}
              y1={PADDING + i * CELL_SIZE}
              x2={PADDING + (boardSize - 1) * CELL_SIZE}
              y2={PADDING + i * CELL_SIZE}
              stroke="#5D4037"
              strokeWidth={i === 0 || i === boardSize - 1 ? 1.5 : 0.8}
            />
            <line
              x1={PADDING + i * CELL_SIZE}
              y1={PADDING}
              x2={PADDING + i * CELL_SIZE}
              y2={PADDING + (boardSize - 1) * CELL_SIZE}
              stroke="#5D4037"
              strokeWidth={i === 0 || i === boardSize - 1 ? 1.5 : 0.8}
            />
          </React.Fragment>
        ))}

        {starPoints.map(([x, y], idx) => {
          const { cx, cy } = posToCoord(x, y);
          return (
            <circle
              key={`star-${idx}`}
              cx={cx}
              cy={cy}
              r={3}
              fill="#5D4037"
            />
          );
        })}

        {/* 棋盘上的棋子 */}
        {stonesOnBoard.map((s) => {
          const { cx, cy } = posToCoord(s.x, s.y);
          const isBlack = s.color === 'B';
          return (
            <g key={`stone-${s.x}-${s.y}`}>
              <circle
                cx={cx}
                cy={cy}
                r={STONE_SIZE / 2}
                fill={isBlack ? 'url(#stone-black)' : 'url(#stone-white)'}
                style={{ filter: 'drop-shadow(2px 2px 2px rgba(0,0,0,0.3))' }}
              />
            </g>
          );
        })}

        {/* 最后一手标记 */}
        {lastMoveInfo && (() => {
          const { cx, cy } = posToCoord(lastMoveInfo.x, lastMoveInfo.y);
          const isBlack = lastMoveInfo.color === 'B';
          return (
            <circle
              cx={cx}
              cy={cy}
              r={6}
              fill="#FF6B35"
              stroke={isBlack ? '#fff' : '#333'}
              strokeWidth={1}
              style={{ pointerEvents: 'none' }}
            />
          );
        })()}

        {/* 推荐手 */}
        {recommendedMoves.map((move, idx) => {
          const x = 'ABCDEFGHJKLMNOPQRST'.indexOf(move.position[0].toUpperCase());
          const y = boardSize - parseInt(move.position.slice(1));
          // 不在已有棋子位置上画推荐
          if (x < 0 || y < 0 || x >= boardSize || y >= boardSize) return null;
          if (boardState.cells[y][x] !== null) return null;

          const { cx, cy } = posToCoord(x, y);
          const opacity = 1 - idx * 0.12;
          // KataGo 默认返回黑棋视角；如果当前轮到白棋，要翻转
          const wr = sideToMove === 'B' ? move.winRate : 100 - move.winRate;
          let fillColor = '#FF9800';
          if (wr >= 60) fillColor = '#10B981';
          else if (wr >= 50) fillColor = '#22C55E';
          else if (wr >= 40) fillColor = '#FACC15';
          else if (wr >= 30) fillColor = '#F97316';
          else fillColor = '#EF4444';

          const isTop = idx === 0;

          return (
            <g key={`rec-${idx}`}>
              {isTop && (
                <circle
                  cx={cx}
                  cy={cy}
                  r={STONE_SIZE / 2 + 2}
                  fill="none"
                  stroke="#FFD700"
                  strokeWidth={2}
                  opacity={0.8}
                />
              )}
              <circle
                cx={cx}
                cy={cy}
                r={STONE_SIZE / 2}
                fill={fillColor}
                opacity={opacity * 0.85}
                stroke="#fff"
                strokeWidth={1.5}
              />
              <text
                x={cx}
                y={cy - 1}
                textAnchor="middle"
                fill="#fff"
                fontSize={10}
                fontWeight="bold"
                style={{ pointerEvents: 'none' }}
              >
                {wr.toFixed(1)}
              </text>
              <text
                x={cx}
                y={cy + 9}
                textAnchor="middle"
                fill="#fff"
                fontSize={7}
                opacity={0.9}
                style={{ pointerEvents: 'none' }}
              >
                {move.visits >= 1000
                  ? `${(move.visits / 1000).toFixed(1)}k`
                  : move.visits}
              </text>
            </g>
          );
        })}

        {/* Hover 预览：在交互模式下显示一个半透明的"幽灵棋子"（最上层，盖过推荐手） */}
        {interactive && onPlayMove && hoverPos && boardState.cells[hoverPos.y]?.[hoverPos.x] === null && (() => {
          const { cx, cy } = posToCoord(hoverPos.x, hoverPos.y);
          const isBlack = sideToMove === 'B';
          return (
            <g style={{ pointerEvents: 'none' }}>
              {/* 外圈淡出阴影，让预览更突出 */}
              <circle
                cx={cx}
                cy={cy}
                r={STONE_SIZE / 2 + 3}
                fill={isBlack ? '#000' : '#fff'}
                opacity={0.15}
              />
              <circle
                cx={cx}
                cy={cy}
                r={STONE_SIZE / 2}
                fill={isBlack ? '#1a1a1a' : '#ffffff'}
                opacity={0.7}
                stroke={isBlack ? '#000' : '#444'}
                strokeWidth={1.5}
              />
            </g>
          );
        })()}
      </svg>

      <div className="absolute top-0 left-0 flex" style={{ marginLeft: PADDING, marginTop: -18 }}>
        {Array.from({ length: boardSize }).map((_, i) => (
          <div
            key={`x-label-${i}`}
            className="text-xs text-go-wood font-medium"
            style={{ width: CELL_SIZE, textAlign: 'center' }}
          >
            {'ABCDEFGHJKLMNOPQRST'[i]}
          </div>
        ))}
      </div>

      <div className="absolute top-0 left-0 flex flex-col" style={{ marginLeft: -18, marginTop: PADDING }}>
        {Array.from({ length: boardSize }).map((_, i) => (
          <div
            key={`y-label-${i}`}
            className="text-xs text-go-wood font-medium"
            style={{ height: CELL_SIZE, lineHeight: `${CELL_SIZE}px`, textAlign: 'right', width: 20 }}
          >
            {boardSize - i}
          </div>
        ))}
      </div>
    </div>
  );
};

export default GoBoard;

