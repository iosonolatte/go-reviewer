# Go-Reviewer 桌面端打包指南

将 Go-Reviewer 打包成跨平台桌面应用 (Windows / macOS / Linux), 一键安装即可使用，无需用户配置 Python / KataGo。

## ⚠️ 重要：在 Trae IDE 中开发的注意事项

Trae IDE 内置的 sandbox 会限制对 `src-tauri/target/` 和 `node_modules/.vite-temp/` 等目录的写入，导致 Tauri 的 Rust 构建脚本和 Vite 临时文件无法生成。

**解决方法**：Tauri 相关命令请在 **Trae 之外的普通 PowerShell 窗口** 运行，例如：

```powershell
# 打开 Windows Terminal 或 PowerShell (不是 Trae 内置终端)
cd C:\Users\allen\Documents\Projects\go-reviewer
npm run tauri:dev
```

或者在 Trae 的 `Settings -> Conversation -> Custom Sandbox Configuration` 添加这两个目录到白名单：
```
C:\Users\<USER>\Documents\Projects\go-reviewer\src-tauri\target
C:\Users\<USER>\Documents\Projects\go-reviewer\node_modules\.vite-temp
```

## 架构

```
┌──────────────────────────────────────────────────┐
│         Tauri Desktop Shell (Rust)               │
│  ┌──────────────────────────────────────────┐    │
│  │  WebView (React + Vite frontend)         │    │
│  │  - 通过 fetch() 调用 http://127.0.0.1:N  │    │
│  └──────────────────────────────────────────┘    │
│              │ window.eval(API_BASE)             │
│              ↓                                   │
│  ┌──────────────────────────────────────────┐    │
│  │  Python Sidecar (PyInstaller-frozen)     │    │
│  │  - go-reviewer-backend.exe (~50MB)       │    │
│  │  - Flask + Tauri 注入端口 + KataGo 路径  │    │
│  └──────────────────────────────────────────┘    │
│              │ subprocess                        │
│              ↓                                   │
│  ┌──────────────────────────────────────────┐    │
│  │  KataGo Engine (bundled OpenCL build)    │    │
│  └──────────────────────────────────────────┘    │
└──────────────────────────────────────────────────┘
```

## 一次性环境准备

### 1. Rust 工具链（必需）

Windows：
```powershell
winget install Rustlang.Rustup
# 或访问 https://rustup.rs/
rustup default stable
```

macOS / Linux：
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

### 2. Tauri 系统依赖

- **Windows**: WebView2（Win10/11 自带）+ Visual Studio Build Tools  
  `winget install Microsoft.VisualStudio.2022.BuildTools` 并勾选 "Desktop development with C++"
- **macOS**: `xcode-select --install`
- **Linux (Ubuntu/Debian)**:
  ```bash
  sudo apt install libwebkit2gtk-4.1-dev build-essential curl wget file libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev
  ```

### 3. Python 后端依赖

```bash
cd backend
pip install -r requirements.txt
pip install pyinstaller
```

### 4. Tauri CLI

```bash
npm install
```

### 5. 应用图标（一次性）

放入 `src-tauri/icons/` 目录：`32x32.png`, `128x128.png`, `128x128@2x.png`, `icon.icns`, `icon.ico`。  
若没有图标，可执行：
```bash
npx @tauri-apps/cli icon path/to/your-logo.png
```

## 开发模式启动

```bash
npm run tauri:dev
```

这会自动：
1. 运行 `python backend/build_backend.py`（首次较慢，约 60s）
2. 启动 Vite dev 服务器（`http://localhost:5173`）
3. 启动 Tauri Rust 主进程，spawn Python sidecar
4. Sidecar 监听一个随机空闲端口
5. 主进程把端口注入到 webview 的 `window.__GO_REVIEWER_API__`

## 生产打包

```bash
npm run tauri:build
```

产物位置：
- **Windows**: `src-tauri/target/release/bundle/nsis/Go-Reviewer_*.exe` 与 `msi/Go-Reviewer_*.msi`
- **macOS**: `src-tauri/target/release/bundle/dmg/Go-Reviewer_*.dmg`
- **Linux**: `src-tauri/target/release/bundle/deb/*.deb` 与 `appimage/*.AppImage`

## 安装包大小估算

| 组件 | 大小 |
|---|---|
| Tauri shell (.exe 主程序) | ~10 MB |
| Python sidecar (PyInstaller) | ~40 MB |
| KataGo + OpenCL DLLs | ~15 MB |
| KataGo b18c384 模型 | ~140 MB |
| **总计** | **~210 MB** |

如需减小：
- 换成 `kata1-b10c128` 小模型（~30MB），总包减到 ~100MB
- 用 `download_on_first_run` 模式（需手动改造）

## 常见问题

### Q: 双击安装包报错 "Backend binary not found"
A: 没有先运行 `npm run build:backend` 生成 sidecar exe。

### Q: 打包后 KataGo 启动失败 "找不到 OpenCL"
A: 确保 `katago-v1.15.3-opencl-windows-x64/` 目录里有 `libcrypto-3-x64.dll` 等所有 dll 文件。Tauri 会作为 resources 整体复制。

### Q: 想换更轻量的 KataGo 模型
A: 编辑 `tauri.conf.json` 的 `bundle.resources` 指向新模型目录，并改 `backend/app.py` 中 `_DEFAULT_MODEL_PATH` 的文件名。

### Q: 调试 Python sidecar 输出
A: Tauri 主进程会把 stdout/stderr 转发为 `backend-log` 事件，前端可监听：
```ts
import { listen } from "@tauri-apps/api/event";
listen<string>("backend-log", (e) => console.log("[backend]", e.payload));
```
也可以查看 Tauri 的日志文件：`%APPDATA%/com.goreviewer.app/logs/`。
