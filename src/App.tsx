import { useEffect } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Home from "./pages/Home";
import Review from "./pages/Review";
import Settings from "./pages/Settings";
import { useGameStore } from "./store/gameStore";

function App() {
  // 启动时从后端同步 KataGo 配置（后端已有预置默认路径）
  const setKatagoConfig = useGameStore((s) => s.setKatagoConfig);
  const katagoConfig = useGameStore((s) => s.katagoConfig);

  useEffect(() => {
    // 仅当前端没有有效路径时，尝试从后端拉取
    if (katagoConfig.path) return;
    fetch("http://localhost:5000/api/config/katago")
      .then((r) => r.json())
      .then((cfg) => {
        if (cfg.path) {
          setKatagoConfig({
            path: cfg.path,
            configPath: cfg.configPath,
            modelPath: cfg.modelPath,
            analyzeTime: cfg.analyzeTime ?? 3,
          });
          console.log("[bootstrap] 已从后端同步 KataGo 配置");
        }
      })
      .catch(() => {
        /* 后端不可用时静默忽略 */
      });
  }, []);

  return (
    <Router>
      <div className="min-h-screen bg-gradient-to-br from-amber-50 via-orange-50 to-yellow-50">
        <Navbar />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/review" element={<Review />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
