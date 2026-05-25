# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for go-reviewer backend
# 用法: pyinstaller go-reviewer-backend.spec  (在 backend/ 目录下)

import sys
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hidden_imports = (
    collect_submodules('flask')
    + collect_submodules('flask_cors')
    + collect_submodules('werkzeug')
    + collect_submodules('openai')
    + [
        'sgf_parser',
        'katago_gtp',
        'katago_analysis',
        'gpu_optimizer',
        'llm_client',
        'engineio.async_drivers.threading',
    ]
)

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy.testing', 'PyQt5', 'PySide2', 'PySide6'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 输出名称根据平台决定 (Tauri externalBin 要求带 target triple 后缀)
import platform
target_triple = {
    ('Windows', 'AMD64'): 'x86_64-pc-windows-msvc',
    ('Windows', 'ARM64'): 'aarch64-pc-windows-msvc',
    ('Darwin', 'x86_64'): 'x86_64-apple-darwin',
    ('Darwin', 'arm64'): 'aarch64-apple-darwin',
    ('Linux', 'x86_64'): 'x86_64-unknown-linux-gnu',
    ('Linux', 'aarch64'): 'aarch64-unknown-linux-gnu',
}.get((platform.system(), platform.machine()), 'unknown')

exe_name = f'go-reviewer-backend-{target_triple}'

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 保留控制台便于排查; Tauri 会用 CREATE_NO_WINDOW 隐藏
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
