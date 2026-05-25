import os
import re
import subprocess
import platform
from typing import Dict, Optional, Tuple


GPU_PROFILES = {
    "high_end_nvidia": {
        "name": "高端 NVIDIA 独显 (RTX 30/40/50 系)",
        "numSearchThreads": 32,
        "nnMaxBatchSize": 128,
        "numAnalysisThreads": 2,
        "numSearchThreadsPerAnalysisThread": 32,
        "description": "强力独显，高并发批处理",
    },
    "mid_nvidia": {
        "name": "中端 NVIDIA 独显 (GTX 16/RTX 20)",
        "numSearchThreads": 24,
        "nnMaxBatchSize": 96,
        "numAnalysisThreads": 2,
        "numSearchThreadsPerAnalysisThread": 24,
        "description": "中端独显，平衡性能",
    },
    "intel_arc_dgpu": {
        "name": "Intel Arc 独显 (A380/A580/A750/A770)",
        "numSearchThreads": 24,
        "nnMaxBatchSize": 96,
        "numAnalysisThreads": 2,
        "numSearchThreadsPerAnalysisThread": 24,
        "description": "Intel 独立显卡，FP16 性能优秀",
    },
    "amd_dgpu": {
        "name": "AMD 独显 (RX 6000/7000 系)",
        "numSearchThreads": 24,
        "nnMaxBatchSize": 96,
        "numAnalysisThreads": 2,
        "numSearchThreadsPerAnalysisThread": 24,
        "description": "AMD 独立显卡",
    },
    "intel_arc_igpu": {
        "name": "Intel Arc 核显 (Core Ultra 系列)",
        "numSearchThreads": 16,
        "nnMaxBatchSize": 64,
        "numAnalysisThreads": 2,
        "numSearchThreadsPerAnalysisThread": 16,
        "description": "Intel Arc 集成显卡，FP16 友好",
    },
    "intel_iris": {
        "name": "Intel Iris/UHD 核显",
        "numSearchThreads": 8,
        "nnMaxBatchSize": 32,
        "numAnalysisThreads": 1,
        "numSearchThreadsPerAnalysisThread": 8,
        "description": "Intel 旧核显，算力较弱",
    },
    "low_end": {
        "name": "低端/未知 GPU",
        "numSearchThreads": 4,
        "nnMaxBatchSize": 16,
        "numAnalysisThreads": 1,
        "numSearchThreadsPerAnalysisThread": 4,
        "description": "保守配置，确保稳定运行",
    },
    "cpu_only": {
        "name": "纯 CPU (无 GPU)",
        "numSearchThreads": 4,
        "nnMaxBatchSize": 8,
        "numAnalysisThreads": 1,
        "numSearchThreadsPerAnalysisThread": 4,
        "description": "无 GPU 加速，速度受限",
    },
}


def detect_gpus(katago_exe: str, model_path: str, timeout: int = 30) -> Dict:
    if not os.path.exists(katago_exe):
        return {"error": f"katago.exe 不存在: {katago_exe}", "devices": []}

    katago_dir = os.path.dirname(katago_exe)
    bench_cfg = os.path.join(katago_dir, "default_gtp.cfg")
    if not os.path.exists(bench_cfg):
        return {"error": "default_gtp.cfg 不存在", "devices": []}
    if not os.path.exists(model_path):
        return {"error": f"模型文件不存在: {model_path}", "devices": []}

    try:
        proc = subprocess.run(
            [katago_exe, "benchmark", "-model", model_path, "-config", bench_cfg, "-t", "4", "-v", "10"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=katago_dir,
        )
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    except subprocess.TimeoutExpired as e:
        output = ""
        if e.stdout:
            output += e.stdout.decode("utf-8", errors="ignore") if isinstance(e.stdout, bytes) else str(e.stdout)
        output += "\n"
        if e.stderr:
            output += e.stderr.decode("utf-8", errors="ignore") if isinstance(e.stderr, bytes) else str(e.stderr)
    except Exception as e:
        return {"error": f"运行 katago benchmark 失败: {e}", "devices": []}

    return _parse_device_output(output)


def _parse_device_output(output: str) -> Dict:
    platforms = []
    devices = []
    selected = None

    for m in re.finditer(r"Found OpenCL Platform (\d+): (.+?) \((.+?)\)", output):
        platforms.append({
            "id": int(m.group(1)),
            "name": m.group(2).strip(),
            "vendor": m.group(3).strip(),
        })

    for m in re.finditer(
        r"Found OpenCL Device (\d+): (.+?) \((.+?)\) \(score (\d+)\)", output
    ):
        devices.append({
            "id": int(m.group(1)),
            "name": m.group(2).strip(),
            "vendor": m.group(3).strip(),
            "score": int(m.group(4)),
        })

    m = re.search(r"Using OpenCL Device (\d+): (.+?) \(", output)
    if m:
        sel_id = int(m.group(1))
        selected = next((d for d in devices if d["id"] == sel_id), None)

    fp16_m = re.search(r"FP16Storage (\w+) FP16Compute (\w+) FP16TensorCores (\w+)", output)
    fp16 = None
    if fp16_m:
        fp16 = {
            "storage": fp16_m.group(1) == "true",
            "compute": fp16_m.group(2) == "true",
            "tensorCores": fp16_m.group(3) == "true",
        }

    return {
        "platforms": platforms,
        "devices": devices,
        "selected_device": selected,
        "fp16": fp16,
        "raw_output": output[-3000:],
    }


def classify_gpu(device: Optional[Dict]) -> str:
    if not device:
        return "cpu_only"

    name = device.get("name", "").lower()
    score = device.get("score", 0)

    if "nvidia" in name or "geforce" in name or "rtx" in name or "gtx" in name or "quadro" in name or "tesla" in name:
        if re.search(r"rtx\s*[345]0", name) or "rtx 30" in name or "rtx 40" in name or "rtx 50" in name:
            return "high_end_nvidia"
        return "mid_nvidia"

    if "arc" in name and re.search(r"\ba\d{3}\b", name):
        return "intel_arc_dgpu"

    if "arc" in name and "graphics" in name:
        return "intel_arc_igpu"

    if "intel" in name and ("iris" in name or "uhd" in name or "hd graphics" in name):
        return "intel_iris"

    if "radeon" in name or "rx " in name or " amd" in name:
        return "amd_dgpu"

    if score >= 5000000:
        return "mid_nvidia"
    if score >= 1000000:
        return "intel_arc_igpu"
    if score > 0:
        return "low_end"
    return "cpu_only"


def generate_optimized_config(
    profile_key: str,
    output_path: str,
    selected_device_id: Optional[int] = None,
) -> Tuple[str, Dict]:
    profile = GPU_PROFILES.get(profile_key, GPU_PROFILES["low_end"])

    lines = [
        "# ===== KataGo 自动优化配置 ({}) =====".format(profile["name"]),
        "# 自动检测生成 - 请勿手动修改, 重新检测时会被覆盖",
        "# Profile: {}".format(profile_key),
        "# 描述: {}".format(profile["description"]),
        "",
        "logToStderr = true",
        "logAllRequests = false",
        "logAllResponses = false",
        "logSearchInfo = false",
        "",
        "reportAnalysisWinratesAs = BLACK",
        "ignorePreRootHistory = true",
        "nnRandomize = false",
        "wideRootNoise = 0.0",
        "",
        "maxVisits = 200",
        "",
        "numAnalysisThreads = {}".format(profile["numAnalysisThreads"]),
        "numSearchThreadsPerAnalysisThread = {}".format(profile["numSearchThreadsPerAnalysisThread"]),
        "nnMaxBatchSize = {}".format(profile["nnMaxBatchSize"]),
        "",
        "nnCacheSizePowerOfTwo = 23",
        "nnMutexPoolSizePowerOfTwo = 17",
    ]

    if selected_device_id is not None and profile_key != "cpu_only":
        lines += [
            "",
            "openclDeviceToUse = {}".format(selected_device_id),
            "numNNServerThreadsPerModel = 1",
        ]

    content = "\n".join(lines) + "\n"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return content, profile


def auto_optimize(katago_exe: str, model_path: str, katago_dir: str) -> Dict:
    detect = detect_gpus(katago_exe, model_path)
    if "error" in detect:
        return {"success": False, "error": detect["error"]}

    selected = detect.get("selected_device")
    profile_key = classify_gpu(selected)

    output_path = os.path.join(katago_dir, "analysis_auto.cfg")
    _, profile = generate_optimized_config(
        profile_key,
        output_path,
        selected_device_id=selected.get("id") if selected else None,
    )

    return {
        "success": True,
        "configPath": output_path,
        "profileKey": profile_key,
        "profile": profile,
        "devices": detect.get("devices", []),
        "selectedDevice": selected,
        "fp16": detect.get("fp16"),
        "platforms": detect.get("platforms", []),
        "system": {
            "os": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
    }
