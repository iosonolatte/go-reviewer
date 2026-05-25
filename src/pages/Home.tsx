import React, { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, FileText, Sparkles, CircleDot, Play } from "lucide-react";
import { useGameStore } from "../store/gameStore";
import { apiUrl } from "../lib/api";

const Home: React.FC = () => {
  const navigate = useNavigate();
  const { setCurrentGame, createEmptyGame } = useGameStore();
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [creatingNew, setCreatingNew] = useState(false);

  const handleStartLive = useCallback(async () => {
    setCreatingNew(true);
    try {
      const response = await fetch(apiUrl("/api/game/new"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ boardSize: 19, komi: 6.5 }),
      });
      if (!response.ok) throw new Error("创建对局失败");
      const data = await response.json();
      // 把 server 分配的 gameId 同步到 store
      setCurrentGame({
        gameId: data.gameId,
        moves: [],
        boardSize: data.boardSize || 19,
        komi: data.komi || 6.5,
        playerBlack: "黑方",
        playerWhite: "白方",
        result: "",
        analyses: {},
      });
      navigate("/review");
    } catch (e) {
      console.error(e);
      // 后端不可用时降级到本地模式
      createEmptyGame(19);
      navigate("/review");
    } finally {
      setCreatingNew(false);
    }
  }, [navigate, setCurrentGame, createEmptyGame]);

  const handleFileUpload = useCallback(
    async (file: File) => {
      if (!file.name.endsWith(".sgf")) {
        alert("请上传 .sgf 格式的棋谱文件");
        return;
      }

      const formData = new FormData();
      formData.append("file", file);

      try {
        setUploadProgress(30);

        const response = await fetch(apiUrl("/api/upload"), {
          method: "POST",
          body: formData,
        });

        setUploadProgress(70);

        if (!response.ok) {
          throw new Error("上传失败");
        }

        const data = await response.json();
        setCurrentGame({
          ...data,
          analyses: {},
        });

        setUploadProgress(100);
        setTimeout(() => {
          navigate("/review");
        }, 500);
      } catch (error) {
        console.error("上传失败:", error);
        alert("棋谱上传失败，请确保后端服务已启动");
        setUploadProgress(0);
      }
    },
    [navigate, setCurrentGame],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);

      const file = e.dataTransfer.files[0];
      if (file) {
        handleFileUpload(file);
      }
    },
    [handleFileUpload],
  );

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileUpload(file);
    }
  };

  const exampleGames = [
    {
      id: 1,
      name: "AlphaGo vs Lee Sedol - 第1局",
      description: "2016年历史性对局，AI首次击败人类顶尖棋手",
      icon: Sparkles,
    },
    {
      id: 2,
      name: "柯洁 vs AlphaGo - 三番棋",
      description: "2017年乌镇围棋峰会，人类与AI的巅峰对决",
      icon: CircleDot,
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-amber-50 via-orange-50 to-yellow-50">
      <div className="max-w-5xl mx-auto px-4 py-12">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-serif text-go-wood mb-4 font-bold">
            智能围棋复盘
          </h1>
          <p className="text-go-woodLight text-lg">
            结合 KataGo 引擎与 AI 大语言模型，让专业复盘触手可及
          </p>
        </div>

        {/* 开始对弈卡片：从空棋盘实时落子 */}
        <button
          onClick={handleStartLive}
          disabled={creatingNew}
          className="w-full mb-6 group relative overflow-hidden rounded-2xl bg-gradient-to-r from-emerald-500 via-green-500 to-teal-500 p-6 shadow-xl hover:shadow-2xl transition-all hover:-translate-y-0.5 disabled:opacity-60 disabled:cursor-not-allowed text-left"
        >
          <div className="absolute inset-0 bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity" />
          <div className="relative flex items-center gap-4">
            <div className="w-14 h-14 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
              <Play className="w-7 h-7 text-white" fill="white" />
            </div>
            <div className="flex-1">
              <h3 className="text-xl font-serif font-bold text-white mb-1">
                {creatingNew ? "正在创建对局..." : "开始实时对弈分析"}
              </h3>
              <p className="text-white/90 text-sm">
                从空棋盘开始，点击棋盘落子，AI 实时分析每一步并给出推荐
              </p>
            </div>
            <div className="text-white/80 text-2xl font-bold pr-2">→</div>
          </div>
        </button>

        <div className="text-center text-go-woodLight text-sm mb-4 flex items-center gap-3">
          <div className="flex-1 h-px bg-go-woodLight/30" />
          <span>或者</span>
          <div className="flex-1 h-px bg-go-woodLight/30" />
        </div>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          className={`relative bg-white rounded-2xl shadow-xl p-8 mb-8 border-2 transition-all duration-300 ${
            isDragging
              ? "border-go-accent bg-orange-50 scale-[1.02]"
              : "border-dashed border-go-woodLight hover:border-go-wood"
          }`}
        >
          <input
            type="file"
            accept=".sgf"
            onChange={handleFileInput}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />

          <div className="text-center">
            <div
              className={`w-20 h-20 mx-auto mb-4 rounded-full flex items-center justify-center transition-all ${
                isDragging ? "bg-go-accent/20 scale-110" : "bg-go-board"
              }`}
            >
              <Upload
                className={`w-10 h-10 transition-colors ${
                  isDragging ? "text-go-accent" : "text-go-wood"
                }`}
              />
            </div>

            <h3 className="text-xl font-serif text-go-wood mb-2 font-medium">
              拖拽棋谱文件到这里
            </h3>
            <p className="text-go-woodLight mb-4">
              或点击选择文件，支持 .sgf 格式
            </p>

            {uploadProgress > 0 && (
              <div className="w-full max-w-md mx-auto">
                <div className="h-2 bg-go-board rounded-full overflow-hidden">
                  <div
                    className="h-full bg-go-accent transition-all duration-500 rounded-full"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
                <p className="text-sm text-go-woodLight mt-2">
                  {uploadProgress < 100 ? "正在处理..." : "处理完成！"}
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-xl p-6 mb-8">
          <h3 className="text-xl font-serif text-go-wood mb-4 font-medium flex items-center gap-2">
            <FileText className="w-5 h-5" />
            示例棋谱
          </h3>

          <div className="grid md:grid-cols-2 gap-4">
            {exampleGames.map((game) => {
              const Icon = game.icon;
              return (
                <button
                  key={game.id}
                  className="p-4 bg-gradient-to-br from-go-board to-go-boardDark rounded-xl text-left hover:shadow-lg transition-all hover:-translate-y-1 group"
                  onClick={() =>
                    alert("请先配置 KataGo 引擎，然后上传您自己的棋谱文件")
                  }
                >
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-lg bg-white/50 flex items-center justify-center flex-shrink-0">
                      <Icon className="w-5 h-5 text-go-wood" />
                    </div>
                    <div>
                      <h4 className="font-medium text-go-wood mb-1 group-hover:text-go-accent transition-colors">
                        {game.name}
                      </h4>
                      <p className="text-sm text-go-woodLight">
                        {game.description}
                      </p>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {[
            {
              title: "KataGo 引擎",
              desc: "最强开源围棋引擎，精准分析每一步的胜率和目差",
              color: "from-blue-500 to-blue-600",
            },
            {
              title: "AI 智能解说",
              desc: "大语言模型将专业分析转化为通俗易懂的讲解",
              color: "from-purple-500 to-purple-600",
            },
            {
              title: "可视化复盘",
              desc: "胜率曲线、推荐变化图，全方位理解棋局",
              color: "from-green-500 to-green-600",
            },
          ].map((feature, idx) => (
            <div
              key={idx}
              className="bg-white rounded-xl p-6 shadow-lg hover:shadow-xl transition-shadow"
            >
              <div
                className={`w-12 h-12 rounded-lg bg-gradient-to-br ${feature.color} mb-4 flex items-center justify-center`}
              >
                <Sparkles className="w-6 h-6 text-white" />
              </div>
              <h4 className="font-serif font-medium text-go-wood text-lg mb-2">
                {feature.title}
              </h4>
              <p className="text-go-woodLight text-sm">{feature.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Home;
