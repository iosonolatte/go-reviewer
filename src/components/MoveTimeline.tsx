import React, { useRef, useEffect } from "react";
import { Move } from "../types";
import { cn } from "../lib/utils";

interface MoveTimelineProps {
  moves: Move[];
  currentMove: number;
  onMoveClick: (moveNumber: number) => void;
}

const MoveTimeline: React.FC<MoveTimelineProps> = ({
  moves,
  currentMove,
  onMoveClick,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current && currentMove > 0) {
      const button = containerRef.current.querySelector(
        `[data-move="${currentMove}"]`,
      ) as HTMLElement;
      if (button) {
        button.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
          inline: "center",
        });
      }
    }
  }, [currentMove]);

  return (
    <div className="bg-white rounded-xl shadow-lg p-4">
      <h3 className="text-lg font-serif text-go-wood mb-3 font-medium">
        落子顺序
      </h3>
      <div
        ref={containerRef}
        className="flex flex-wrap gap-2 max-h-40 overflow-y-auto p-1"
      >
        {moves.map((move, idx) => {
          const moveNum = idx + 1;
          const isCurrent = moveNum === currentMove;
          const isBlack = move.color === "B";

          return (
            <button
              key={idx}
              data-move={moveNum}
              onClick={() => onMoveClick(moveNum)}
              className={cn(
                "w-10 h-10 rounded-lg flex items-center justify-center text-sm font-medium transition-all",
                isCurrent
                  ? "ring-2 ring-go-accent ring-offset-2 scale-110"
                  : "hover:scale-105",
                isBlack
                  ? "bg-go-black text-white shadow-stone"
                  : "bg-go-white text-go-black border border-gray-300 shadow-stone",
              )}
            >
              {moveNum}
            </button>
          );
        })}
      </div>
      <div className="flex justify-between text-sm text-go-woodLight mt-3 pt-3 border-t border-gray-100">
        <span>共 {moves.length} 手</span>
        <span>当前：第 {currentMove} 手</span>
      </div>
    </div>
  );
};

export default MoveTimeline;
