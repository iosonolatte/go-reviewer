/**
 * 集中管理后端 API base URL
 * - 开发模式: 默认 http://localhost:5000 (Flask 开发服)
 * - Tauri 桌面版: 通过 window.__GO_REVIEWER_API__ 注入实际端口 (主进程动态分配)
 * - 也可通过 Vite 环境变量 VITE_API_BASE 覆盖
 */

declare global {
  interface Window {
    __GO_REVIEWER_API__?: string;
    __TAURI__?: unknown;
    __TAURI_INTERNALS__?: unknown;
  }
}

export function isTauri(): boolean {
  return (
    typeof window !== "undefined" &&
    (!!window.__TAURI__ || !!window.__TAURI_INTERNALS__)
  );
}

let _apiBase: string | null = null;
let _readyPromise: Promise<string> | null = null;

function detectApiBase(): string {
  if (typeof window !== "undefined" && window.__GO_REVIEWER_API__) {
    return window.__GO_REVIEWER_API__.replace(/\/+$/, "");
  }
  const envBase = import.meta.env.VITE_API_BASE as string | undefined;
  if (envBase) return envBase.replace(/\/+$/, "");
  return "http://localhost:5000";
}

/** 等待 Tauri 主进程注入 __GO_REVIEWER_API__, 最多 30s */
function waitForApiInjection(): Promise<string> {
  if (_readyPromise) return _readyPromise;
  _readyPromise = new Promise<string>((resolve) => {
    if (typeof window === "undefined") {
      resolve("http://localhost:5000");
      return;
    }
    if (window.__GO_REVIEWER_API__) {
      resolve(window.__GO_REVIEWER_API__);
      return;
    }
    if (!isTauri()) {
      resolve(detectApiBase());
      return;
    }
    const onReady = (e: Event) => {
      const detail = (e as CustomEvent<string>).detail;
      window.removeEventListener("go-reviewer-ready", onReady);
      resolve(detail || detectApiBase());
    };
    window.addEventListener("go-reviewer-ready", onReady);
    setTimeout(() => {
      window.removeEventListener("go-reviewer-ready", onReady);
      resolve(detectApiBase());
    }, 30_000);
  });
  return _readyPromise;
}

export function getApiBase(): string {
  if (_apiBase) return _apiBase;
  _apiBase = detectApiBase();
  return _apiBase;
}

export const API_BASE = getApiBase();

export function apiUrl(path: string): string {
  if (!path.startsWith("/")) path = "/" + path;
  return getApiBase() + path;
}

export async function whenBackendReady(): Promise<string> {
  const base = await waitForApiInjection();
  _apiBase = base.replace(/\/+$/, "");
  return _apiBase;
}
