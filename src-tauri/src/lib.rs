// Go-Reviewer Tauri shell entry
// 职责: 启动 Python sidecar (PyInstaller 打包的后端), 等待 ready 信号, 注入 API URL 到 webview, 退出时清理子进程

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;
use std::thread;
use std::time::Duration;

use once_cell::sync::Lazy;
use tauri::{AppHandle, Emitter, Manager, RunEvent};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

static BACKEND_PROCESS: Lazy<Mutex<Option<CommandChild>>> = Lazy::new(|| Mutex::new(None));
static BACKEND_PORT: Lazy<Mutex<Option<u16>>> = Lazy::new(|| Mutex::new(None));

fn pick_free_port() -> u16 {
    portpicker::pick_unused_port().unwrap_or(50725)
}

/// 启动 Python sidecar 后端
fn spawn_backend(app: &AppHandle, port: u16) -> Result<CommandChild, String> {
    // KataGo 资源目录 (打包后位于 Resources, 开发模式由 tauri.conf.json 的 resources 字段映射)
    let katago_dir = app
        .path()
        .resolve("katago", tauri::path::BaseDirectory::Resource)
        .map_err(|e| format!("Cannot resolve katago dir: {e}"))?;

    // 用户数据目录 (跨平台)
    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("Cannot resolve app_data_dir: {e}"))?;

    if !data_dir.exists() {
        let _ = std::fs::create_dir_all(&data_dir);
    }

    log::info!("KataGo dir: {}", katago_dir.display());
    log::info!("Data dir: {}", data_dir.display());
    log::info!("Backend port: {}", port);

    // tauri-plugin-shell 的 sidecar API 自动处理 target triple 后缀
    let sidecar = app
        .shell()
        .sidecar("go-reviewer-backend")
        .map_err(|e| format!("Failed to locate sidecar 'go-reviewer-backend': {e}"))?
        .args([
            "--prod",
            "--port",
            &port.to_string(),
            "--host",
            "127.0.0.1",
        ])
        .env("GO_REVIEWER_KATAGO_DIR", katago_dir.to_string_lossy().to_string())
        .env("GO_REVIEWER_DATA_DIR", data_dir.to_string_lossy().to_string())
        .env("GO_REVIEWER_PORT", port.to_string());

    let (mut rx, child) = sidecar
        .spawn()
        .map_err(|e| format!("Failed to spawn backend: {e}"))?;

    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line_bytes) => {
                    let line = String::from_utf8_lossy(&line_bytes).to_string();
                    log::info!("[backend] {line}");
                    let _ = app_handle.emit("backend-log", line);
                }
                CommandEvent::Stderr(line_bytes) => {
                    let line = String::from_utf8_lossy(&line_bytes).to_string();
                    log::warn!("[backend!] {line}");
                    let _ = app_handle.emit("backend-log", line);
                }
                CommandEvent::Terminated(payload) => {
                    log::warn!("Backend terminated: code={:?}", payload.code);
                    let _ = app_handle.emit(
                        "backend-terminated",
                        format!("Exit code: {:?}", payload.code),
                    );
                    break;
                }
                _ => {}
            }
        }
    });

    Ok(child)
}

/// 轮询健康检查, 等待后端就绪
fn wait_for_backend_ready(port: u16, timeout_secs: u64) -> bool {
    let url = format!("http://127.0.0.1:{port}/api/health");
    let deadline = std::time::Instant::now() + Duration::from_secs(timeout_secs);
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
        .ok();

    while std::time::Instant::now() < deadline {
        if let Some(c) = &client {
            if let Ok(resp) = c.get(&url).send() {
                if resp.status().is_success() {
                    return true;
                }
            }
        }
        thread::sleep(Duration::from_millis(300));
    }
    false
}

/// Tauri command: 前端可以查询当前后端 API 地址
#[tauri::command]
fn get_api_base() -> String {
    let port = BACKEND_PORT.lock().unwrap().unwrap_or(5000);
    format!("http://127.0.0.1:{port}")
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_log::Builder::new().build())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![get_api_base])
        .setup(|app| {
            let handle = app.handle().clone();

            // 1) 选一个空闲端口
            let port = pick_free_port();
            *BACKEND_PORT.lock().unwrap() = Some(port);

            // 2) 启动后端 sidecar
            match spawn_backend(&handle, port) {
                Ok(child) => {
                    *BACKEND_PROCESS.lock().unwrap() = Some(child);
                }
                Err(e) => {
                    log::error!("Backend spawn failed: {e}");
                    let _ = handle.emit("backend-error", e);
                }
            }

            // 3) 异步等待后端 ready 后注入 API URL 到 webview
            let handle2 = handle.clone();
            thread::spawn(move || {
                let ready = wait_for_backend_ready(port, 60);
                let api_base = format!("http://127.0.0.1:{port}");
                if let Some(window) = handle2.get_webview_window("main") {
                    if ready {
                        let js = format!(
                            "window.__GO_REVIEWER_API__ = {q}; window.dispatchEvent(new CustomEvent('go-reviewer-ready', {{ detail: {q} }}));",
                            q = serde_json::to_string(&api_base).unwrap()
                        );
                        let _ = window.eval(&js);
                        let _ = handle2.emit("backend-ready", &api_base);
                        log::info!("Backend ready at {api_base}");
                    } else {
                        let _ = handle2.emit("backend-error", "Backend did not become ready in time");
                        log::error!("Backend did not become ready in time");
                    }
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(|_app_handle, event| {
            // 关闭主窗口时, 杀掉后端 sidecar
            if let RunEvent::ExitRequested { .. } | RunEvent::Exit = event {
                if let Some(child) = BACKEND_PROCESS.lock().unwrap().take() {
                    log::info!("Killing backend sidecar (pid={})", child.pid());
                    let _ = child.kill();
                }
            }
        });
}
