import { useEffect, useState } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Home from "./pages/Home";
import Review from "./pages/Review";
import Settings from "./pages/Settings";
import { useGameStore } from "./store/gameStore";
import { apiUrl, isTauri, whenBackendReady } from "./lib/api";

function App() {
  // 启动时从后端同步 KataGo 配置（后端已有预置默认路径）
  const setKatagoConfig = useGameStore((s) => s.setKatagoConfig);
  const katagoConfig = useGameStore((s) => s.katagoConfig);

  // Tauri 桌面版需等后端 sidecar 就绪后才能调用 API
  const [backendReady, setBackendReady] = useState(!isTauri());

  useEffect(() => {
    if (!isTauri()) return;
    whenBackendReady()
      .then(() => setBackendReady(true))
      .catch(() => setBackendReady(true));
  }, []);

  useEffect(() => {
    if (!backendReady) return;
    if (katagoConfig.path) return;
    fetch(apiUrl("/api/config/katago"))
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
  }, [backendReady]);

  if (!backendReady) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-amber-50 via-orange-50 to-yellow-50">
        <div className="text-center">
          <div className="inline-block w-12 h-12 border-4 border-amber-300 border-t-amber-700 rounded-full animate-spin mb-4" />
          <h2 className="text-xl font-serif text-go-wood">
            正在启动 KataGo 引擎…
          </h2>
          <p className="text-sm text-go-woodLight mt-2">
            首次启动会进行 GPU 自适应调优，请稍候
          </p>
        </div>
      </div>
    );
  }

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
