"""
打包 Python 后端为单文件 exe, 并复制到 src-tauri/binaries/
用法: python backend/build_backend.py  (在项目根或 backend/ 都可)
"""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    backend_dir = Path(__file__).resolve().parent
    project_dir = backend_dir.parent
    spec_file = backend_dir / "go-reviewer-backend.spec"
    dist_dir = backend_dir / "dist"
    build_dir = backend_dir / "build"
    target_dir = project_dir / "src-tauri" / "binaries"

    if not spec_file.exists():
        sys.exit(f"❌ Spec file not found: {spec_file}")

    target_dir.mkdir(parents=True, exist_ok=True)

    # 1) 确保 PyInstaller 可用
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("📦 PyInstaller 未安装, 正在安装…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 2) 清理旧产物
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)

    # 3) 运行 PyInstaller
    print(f"🔨 构建后端 sidecar (运行 pyinstaller)...")
    subprocess.check_call(
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(spec_file)],
        cwd=str(backend_dir),
    )

    # 4) 推断 target triple, 与 spec 文件一致
    target_triple = {
        ("Windows", "AMD64"): "x86_64-pc-windows-msvc",
        ("Windows", "ARM64"): "aarch64-pc-windows-msvc",
        ("Darwin", "x86_64"): "x86_64-apple-darwin",
        ("Darwin", "arm64"): "aarch64-apple-darwin",
        ("Linux", "x86_64"): "x86_64-unknown-linux-gnu",
        ("Linux", "aarch64"): "aarch64-unknown-linux-gnu",
    }.get((platform.system(), platform.machine()), "unknown")

    exe_suffix = ".exe" if platform.system() == "Windows" else ""
    src_exe = dist_dir / f"go-reviewer-backend-{target_triple}{exe_suffix}"

    if not src_exe.exists():
        # PyInstaller 可能输出到 dist/<name>/<name>.exe 或 dist/<name>.exe
        candidates = list(dist_dir.rglob(f"go-reviewer-backend-{target_triple}{exe_suffix}"))
        if candidates:
            src_exe = candidates[0]
        else:
            sys.exit(f"❌ Built exe not found in {dist_dir}")

    # 5) 复制到 src-tauri/binaries/
    dst_exe = target_dir / src_exe.name
    shutil.copy2(src_exe, dst_exe)
    print(f"✅ 后端构建完成: {dst_exe}")

    # 同时给 Tauri 的 externalBin 配置一个无 target triple 的副本(用于 dev 模式)
    short_name = f"go-reviewer-backend{exe_suffix}"
    short_dst = target_dir / short_name
    shutil.copy2(src_exe, short_dst)
    print(f"✅ 副本 (dev): {short_dst}")

    print()
    print("📋 下一步:")
    print("   cd src-tauri && cargo tauri dev      # 开发模式启动桌面端")
    print("   cd src-tauri && cargo tauri build    # 打包安装包 (NSIS / MSI)")


if __name__ == "__main__":
    main()
