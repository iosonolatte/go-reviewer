import os
import sys
import uuid
import json
import tempfile
import traceback
import threading
from typing import List, Dict
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

from sgf_parser import SGFParser
from katago_gtp import get_engine, reset_engine
from katago_analysis import (
    get_analysis_engine,
    reset_analysis_engine,
    parse_analysis_response
)
from gpu_optimizer import auto_optimize, GPU_PROFILES

app = Flask(__name__)
CORS(app)

# ---- 路径常量 ----
# 兼容三种运行环境:
#   1. 开发模式 (python backend/app.py): __file__ 在 backend/, KataGo 在 PROJECT_DIR/katago-...
#   2. PyInstaller 单文件打包 (sys.frozen): KataGo 资源被解压到 sys._MEIPASS, 但用户文件在 exe 同目录
#   3. Tauri sidecar 运行: exe 位于 src-tauri/binaries/, 资源由 Tauri resource 提供
def _resolve_katago_dir() -> str:
    # 环境变量优先 (Tauri 启动时注入)
    env_dir = os.environ.get("GO_REVIEWER_KATAGO_DIR")
    if env_dir and os.path.isdir(env_dir):
        return env_dir

    if getattr(sys, "frozen", False):
        # PyInstaller 打包后, exe 同目录或上级目录寻找
        exe_dir = os.path.dirname(sys.executable)
        for candidate in [
            os.path.join(exe_dir, "katago"),
            os.path.join(exe_dir, "..", "katago"),
            os.path.join(exe_dir, "..", "..", "Resources", "katago"),
        ]:
            if os.path.isdir(candidate):
                return os.path.abspath(candidate)
        return os.path.abspath(os.path.join(exe_dir, "katago"))

    # 开发模式
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(backend_dir)
    return os.path.join(project_dir, "katago-v1.15.3-opencl-windows-x64")


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BACKEND_DIR)
KATAGO_DIR = _resolve_katago_dir()
print(f"[init] KataGo dir: {KATAGO_DIR}")

# 持久化配置：用户数据目录 (跨平台)
def _resolve_config_dir() -> str:
    env_dir = os.environ.get("GO_REVIEWER_DATA_DIR")
    if env_dir:
        os.makedirs(env_dir, exist_ok=True)
        return env_dir
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
        d = os.path.join(base, "go-reviewer")
    elif sys.platform == "darwin":
        d = os.path.expanduser("~/Library/Application Support/go-reviewer")
    else:
        d = os.path.expanduser("~/.local/share/go-reviewer")
    try:
        os.makedirs(d, exist_ok=True)
        # 写入测试
        test_file = os.path.join(d, ".write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return d
    except Exception:
        return os.path.join(tempfile.gettempdir(), "go-reviewer")


_CONFIG_DIR = _resolve_config_dir()
os.makedirs(_CONFIG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(_CONFIG_DIR, "config.json")
print(f"[init] Config file: {CONFIG_FILE}")

# 上传文件夹
UPLOAD_FOLDER = os.path.join(_CONFIG_DIR, "uploads")
try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except Exception:
    UPLOAD_FOLDER = tempfile.gettempdir()
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
print(f"[init] Upload folder: {UPLOAD_FOLDER}")

# ---- 全局存储 + 线程锁 (#8) ----
_games_lock = threading.Lock()
games_store: Dict[str, dict] = {}

_config_lock = threading.Lock()

# games 持久化文件路径 (#6) — 仅存元数据和棋步，不存分析（可重算）
GAMES_FILE = os.path.join(_CONFIG_DIR, "games.json")


def _games_get(game_id: str):
    """线程安全地读取一局棋。不存在返回 None。"""
    with _games_lock:
        return games_store.get(game_id)


def _games_set(game_id: str, game: dict):
    """线程安全地写入一局棋，并持久化到磁盘。"""
    with _games_lock:
        games_store[game_id] = game
        _save_games_locked()


def _games_del(game_id: str):
    """线程安全地删除一局棋。"""
    with _games_lock:
        games_store.pop(game_id, None)
        _save_games_locked()


def _save_games_locked():
    """持久化 games_store（调用方须已持有 _games_lock）。
    只保存元数据和棋步；analyses 不持久化（可在会话中重算）。
    """
    try:
        snapshot = {}
        for gid, g in games_store.items():
            snapshot[gid] = {
                k: v for k, v in g.items() if k != "analyses"
            }
        tmp = GAMES_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False)
        os.replace(tmp, GAMES_FILE)  # 原子替换，避免写一半损坏
    except Exception as e:
        print(f"[games] 持久化失败 (忽略): {e}")


def load_games():
    """启动时从磁盘恢复 games_store（analyses 重置为空）。"""
    if not os.path.exists(GAMES_FILE):
        return
    try:
        with open(GAMES_FILE, "r", encoding="utf-8") as f:
            saved: dict = json.load(f)
        with _games_lock:
            for gid, g in saved.items():
                g.setdefault("analyses", {})
                games_store[gid] = g
        print(f"[init] 已恢复 {len(saved)} 局棋谱")
    except Exception as e:
        print(f"[init] 恢复棋谱失败 (忽略): {e}")


# ---- 预置默认 KataGo 路径，首次启动即可用 ----
# 适配不同平台的可执行文件名
_KATAGO_EXE_NAME = "katago.exe" if sys.platform == "win32" else "katago"
_DEFAULT_KATAGO_PATH = os.path.join(KATAGO_DIR, _KATAGO_EXE_NAME)
_DEFAULT_CONFIG_PATH = os.path.join(KATAGO_DIR, "analysis_fast.cfg")
_DEFAULT_MODEL_PATH = os.path.join(KATAGO_DIR, "kata1-b18c384nbt.bin.gz")

config_store = {
    "katago": {
        "path": _DEFAULT_KATAGO_PATH if os.path.exists(_DEFAULT_KATAGO_PATH) else "",
        "configPath": _DEFAULT_CONFIG_PATH if os.path.exists(_DEFAULT_CONFIG_PATH) else "",
        "modelPath": _DEFAULT_MODEL_PATH if os.path.exists(_DEFAULT_MODEL_PATH) else "",
        "analyzeTime": 3
    },
    "llm": {
        "apiKey": "",
        "model": "gpt-4",
        "baseUrl": None
    }
}


def load_config():
    global config_store
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if "katago" in saved:
                    config_store["katago"].update(saved["katago"])
                if "llm" in saved:
                    config_store["llm"].update(saved["llm"])
            print(f"[init] 已加载持久化配置: katago.path={config_store['katago']['path']!r}")
        except Exception as e:
            print(f"[init] 加载配置失败: {e}")
    else:
        # 尝试从旧位置迁移配置
        _migrate_old_config()
        if not os.path.exists(CONFIG_FILE):
            # 首次启动：将代码默认值写入磁盘
            save_config()
            print(f"[init] 已写入默认配置")


def _migrate_old_config():
    """从旧版本配置路径迁移到新路径 (v0.0 的 %TEMP%/go-reviewer/)"""
    old_path = os.path.join(tempfile.gettempdir(), "go-reviewer", "config.json")
    if os.path.exists(old_path) and old_path != CONFIG_FILE:
        try:
            with open(old_path, "r", encoding="utf-8") as f:
                old = json.load(f)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(old, f, ensure_ascii=False, indent=2)
            print(f"[init] 已从旧配置迁移: {old_path} → {CONFIG_FILE}")
        except Exception as e:
            print(f"[init] 迁移旧配置失败 (忽略): {e}")


def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_store, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[config] 保存配置失败: {e}")


load_config()
load_games()


def is_katago_configured() -> bool:
    cfg = config_store["katago"]
    return all([
        cfg.get("path"),
        cfg.get("configPath"),
        cfg.get("modelPath"),
        os.path.exists(cfg.get("path", "")),
        os.path.exists(cfg.get("configPath", "")),
        os.path.exists(cfg.get("modelPath", "")),
    ])


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "katagoConfigured": is_katago_configured(),
        "katagoDir": KATAGO_DIR,
        "configDir": _CONFIG_DIR,
    })


@app.route("/api/config/katago", methods=["POST"])
def set_katago_config():
    data = request.json
    with _config_lock:
        config_store["katago"].update(data)
        save_config()
    reset_engine()
    reset_analysis_engine()
    print(f"[config] KataGo 配置已更新: path={config_store['katago']['path']!r}, configured={is_katago_configured()}")
    return jsonify({"success": True, "config": config_store["katago"], "configured": is_katago_configured()})


@app.route("/api/config/katago", methods=["GET"])
def get_katago_config():
    return jsonify(config_store["katago"])


@app.route("/api/config/llm", methods=["POST"])
def set_llm_config():
    data = request.json
    with _config_lock:
        config_store["llm"].update(data)
        save_config()
    return jsonify({"success": True, "config": config_store["llm"]})


@app.route("/api/config/llm", methods=["GET"])
def get_llm_config():
    return jsonify(config_store["llm"])


@app.route("/api/gpu/auto-optimize", methods=["POST"])
def gpu_auto_optimize():
    """检测当前 GPU 并生成最优 analysis_auto.cfg"""
    katago_path = config_store["katago"].get("path") or _DEFAULT_KATAGO_PATH
    model_path = config_store["katago"].get("modelPath") or _DEFAULT_MODEL_PATH

    if not os.path.exists(katago_path):
        return jsonify({"success": False, "error": f"katago.exe 不存在: {katago_path}"}), 400
    if not os.path.exists(model_path):
        return jsonify({"success": False, "error": f"模型文件不存在: {model_path}"}), 400

    # 优先写入 KataGo 目录(便于用户查看), 失败则降级到 temp 目录
    try:
        result = auto_optimize(katago_path, model_path, KATAGO_DIR)
    except PermissionError:
        result = auto_optimize(katago_path, model_path, _CONFIG_DIR)

    if result.get("success") and result.get("configPath"):
        # 自动应用为当前配置
        config_store["katago"]["configPath"] = result["configPath"]
        save_config()
        reset_analysis_engine()
        reset_engine()
        result["applied"] = True

    return jsonify(result)


@app.route("/api/gpu/profiles", methods=["GET"])
def gpu_profiles():
    """返回所有 GPU profile 定义, 供前端展示"""
    return jsonify({"profiles": GPU_PROFILES})


@app.route("/api/upload", methods=["POST"])
def upload_sgf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not file.filename.endswith(".sgf"):
        return jsonify({"error": "Invalid file format"}), 400

    try:
        sgf_bytes = file.read()
        try:
            sgf_content = sgf_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                sgf_content = sgf_bytes.decode("gbk")
            except UnicodeDecodeError:
                sgf_content = sgf_bytes.decode("utf-8", errors="replace")

        game_id = str(uuid.uuid4())

        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], f"{game_id}.sgf")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(sgf_content)
        except (PermissionError, OSError) as e:
            print(f"[upload] 跳过磁盘缓存（{e}），仅保存到内存")

        parsed = SGFParser.parse(sgf_content)
        _games_set(game_id, {
            "sgfContent": sgf_content,
            "moves": parsed["moves"],
            "boardSize": parsed["boardSize"],
            "komi": parsed["komi"],
            "playerBlack": parsed["playerBlack"],
            "playerWhite": parsed["playerWhite"],
            "result": parsed["result"],
            "analyses": {},
            "lastPlayedMove": 0
        })

        return jsonify({
            "gameId": game_id,
            "moves": parsed["moves"],
            "boardSize": parsed["boardSize"],
            "playerBlack": parsed["playerBlack"],
            "playerWhite": parsed["playerWhite"],
            "result": parsed["result"]
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"上传失败: {str(e)}"}), 500


@app.route("/api/game/<game_id>", methods=["GET"])
def get_game(game_id):
    game = _games_get(game_id)
    if game is None:
        return jsonify({"error": "Game not found"}), 404

    return jsonify({
        "gameId": game_id,
        "moves": game["moves"],
        "boardSize": game["boardSize"],
        "playerBlack": game["playerBlack"],
        "playerWhite": game["playerWhite"],
        "result": game["result"]
    })


@app.route("/api/game/new", methods=["POST"])
def new_game():
    """创建一个空白对局，用于实时落子模式"""
    data = request.json or {}
    board_size = data.get("boardSize", 19)
    komi = data.get("komi", 6.5)

    game_id = str(uuid.uuid4())
    _games_set(game_id, {
        "sgfContent": "",
        "moves": [],
        "boardSize": board_size,
        "komi": komi,
        "playerBlack": data.get("playerBlack", "黑方"),
        "playerWhite": data.get("playerWhite", "白方"),
        "result": "",
        "analyses": {},
        "lastPlayedMove": 0,
        "isLive": True
    })
    print(f"[live] 新建实时对局: {game_id}, 棋盘 {board_size}x{board_size}, 贴目 {komi}")
    return jsonify({
        "gameId": game_id,
        "boardSize": board_size,
        "komi": komi,
        "moves": []
    })


@app.route("/api/game/<game_id>/play", methods=["POST"])
def play_move(game_id):
    """实时落子：追加一手到对局"""
    game = _games_get(game_id)
    if game is None:
        return jsonify({"error": "Game not found"}), 404

    data = request.json or {}
    color = data.get("color")
    position = data.get("position")

    if color not in ("B", "W"):
        return jsonify({"error": "Invalid color"}), 400
    if not position:
        return jsonify({"error": "Missing position"}), 400

    # 把 KataGo 坐标 (如 Q16) 转回 (x,y)
    LETTERS = "ABCDEFGHJKLMNOPQRST"
    try:
        letter = position[0].upper()
        num = int(position[1:])
        x = LETTERS.index(letter)
        y = game["boardSize"] - num
    except (ValueError, IndexError):
        return jsonify({"error": f"Invalid position: {position}"}), 400

    with _games_lock:
        move_num = len(game["moves"]) + 1
        game["moves"].append({
            "number": move_num,
            "color": color,
            "position": position,
            "x": x,
            "y": y
        })
        game["lastPlayedMove"] = move_num
        _save_games_locked()

    return jsonify({
        "success": True,
        "moveNumber": move_num,
        "moves": game["moves"]
    })


@app.route("/api/game/<game_id>/undo", methods=["POST"])
def undo_move(game_id):
    """实时落子：悔棋"""
    game = _games_get(game_id)
    if game is None:
        return jsonify({"error": "Game not found"}), 404

    with _games_lock:
        if not game["moves"]:
            return jsonify({"error": "No moves to undo"}), 400

        removed = game["moves"].pop()
        game["lastPlayedMove"] = len(game["moves"])
        # 清除该手及之后的分析缓存
        move_num = removed.get("number", removed.get("moveNumber", 0))
        for k in list(game["analyses"].keys()):
            if k >= move_num:
                del game["analyses"][k]
        _save_games_locked()

    return jsonify({
        "success": True,
        "removed": removed,
        "moves": game["moves"]
    })


def _mock_analysis(move_number: int):
    import random
    random.seed(move_number)
    base_rate = 50 + (move_number % 7) * 2 - 6
    moves = []
    letters = "ABCDEFGHJKLMNOPQRST"
    for i in range(5):
        letter = letters[random.randint(2, 16)]
        num = random.randint(3, 17)
        moves.append({
            "position": f"{letter}{num}",
            "winRate": round(base_rate + random.uniform(-2, 2), 2),
            "visits": random.randint(100, 1500)
        })
    moves.sort(key=lambda m: m["visits"], reverse=True)
    return {
        "moveNumber": move_number,
        "winRate": round(base_rate, 2),
        "scoreLead": round(random.uniform(-5, 5), 2),
        "recommendedMoves": moves,
        "isMock": True
    }


@app.route("/api/analyze/<game_id>/<int:move_number>", methods=["GET"])
def analyze_move(game_id, move_number):
    game = _games_get(game_id)
    if game is None:
        return jsonify({"error": "Game not found"}), 404

    if move_number in game["analyses"]:
        return jsonify(game["analyses"][move_number])

    if not is_katago_configured():
        cfg = config_store["katago"]
        reasons = []
        if not cfg.get("path"):
            reasons.append("可执行文件路径为空")
        elif not os.path.exists(cfg["path"]):
            reasons.append(f"可执行文件不存在: {cfg['path']}")
        if not cfg.get("configPath"):
            reasons.append("配置文件路径为空")
        elif not os.path.exists(cfg["configPath"]):
            reasons.append(f"配置文件不存在: {cfg['configPath']}")
        if not cfg.get("modelPath"):
            reasons.append("权重文件路径为空")
        elif not os.path.exists(cfg["modelPath"]):
            reasons.append(f"权重文件不存在: {cfg['modelPath']}")

        print(f"[analyze] 第 {move_number} 手 - 使用 mock 数据，原因: {'; '.join(reasons)}")
        analysis = _mock_analysis(move_number)
        analysis["mockReasons"] = reasons
        game["analyses"][move_number] = analysis
        return jsonify(analysis)

    # 优先使用 Analysis Engine（速度快、稳定）
    try:
        cfg = config_store["katago"]
        is_human = "human" in (cfg["modelPath"] or "").lower()
        human_profile = "preaz_9d" if is_human else None
        # analyzeTime 现在直接被解释为 visits 上限
        # 1=极速(250), 3=快(750), 5=均衡(1250), 10=精确(2500), 20=深度(5000)
        analyze_time = config_store["katago"].get("analyzeTime", 3)
        # 允许前端在 query 参数里临时覆盖
        override_visits = request.args.get("visits", type=int)
        if override_visits and override_visits > 0:
            max_visits = override_visits
        else:
            max_visits = max(100, min(5000, analyze_time * 250))

        print(f"[analyze] 第 {move_number} 手 - 使用 Analysis Engine (maxVisits={max_visits})")
        engine = get_analysis_engine(cfg["path"], cfg["configPath"], cfg["modelPath"])
        moves_list = _moves_to_analysis_format(game["moves"], len(game["moves"]))
        response = engine.analyze_position(
            moves=moves_list,
            board_size=game["boardSize"],
            komi=game.get("komi", 6.5),
            max_visits=max_visits,
            humanSL_profile=human_profile,
            analyze_turn=move_number,
            timeout=60
        )

        if "error" in response:
            raise RuntimeError(response.get("error", "未知错误"))

        parsed = parse_analysis_response(response)
        analysis = {
            "moveNumber": move_number,
            "winRate": parsed["winRate"] if parsed["winRate"] is not None else 50.0,
            "scoreLead": parsed["scoreLead"] if parsed["scoreLead"] is not None else 0.0,
            "recommendedMoves": parsed["recommendedMoves"],
            "totalVisits": parsed["totalVisits"],
            "isMock": False,
            "method": "analysis"
        }
        print(f"[analyze] 完成: winRate={analysis['winRate']}%, recs={len(analysis['recommendedMoves'])}, visits={analysis['totalVisits']}")
        game["analyses"][move_number] = analysis
        return jsonify(analysis)

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": f"分析失败: {str(e)}",
            "hint": "Analysis 引擎遇到问题，请检查后端日志"
        }), 500


@app.route("/api/commentary/<game_id>/<int:move_number>", methods=["GET"])
def get_commentary(game_id, move_number):
    game = _games_get(game_id)
    if game is None:
        return jsonify({"error": "Game not found"}), 404

    if move_number not in game["analyses"]:
        return jsonify({"error": "Analysis not available"}), 400

    analysis = game["analyses"][move_number]
    move = game["moves"][move_number - 1] if move_number > 0 else None

    move_color = move.get("color") if move else "B"
    color_name = "黑" if move_color == "B" else "白"

    # 下一手轮到谁：本手是黑则下一手白
    next_side = "W" if move_color == "B" else "B"
    next_side_name = "黑" if next_side == "B" else "白"

    # KataGo 返回的胜率/目差是黑棋视角，根据下一手方转换
    win_rate_black = analysis.get("winRate", 50.0) or 50.0
    score_lead_black = analysis.get("scoreLead", 0.0) or 0.0

    next_win_rate = win_rate_black if next_side == "B" else 100 - win_rate_black
    next_score_lead = score_lead_black if next_side == "B" else -score_lead_black

    rec_lines = []
    for idx, rm in enumerate(analysis.get("recommendedMoves", [])[:3], 1):
        # 同样转换为下一手方视角的胜率
        wr = rm["winRate"] if next_side == "B" else 100 - rm["winRate"]
        rec_lines.append(
            f"{idx}. {rm['position']}（{next_side_name}棋胜率 {wr:.1f}%，访问 {rm['visits']} 次）"
        )
    rec_text = "\n".join(rec_lines) if rec_lines else "（暂无推荐）"

    prev_rate = None
    prev_num = move_number - 1
    if prev_num in game["analyses"]:
        prev_rate = game["analyses"][prev_num].get("winRate")

    if prev_rate is not None:
        diff = win_rate_black - prev_rate
        # 从下手方角度看胜率变化
        # 当前手是 move_color 下的，move_color 想让自己的胜率提升
        if move_color == "B":
            move_rate_change = diff
        else:
            move_rate_change = -diff

        if abs(move_rate_change) < 3:
            judge = "这一手是正常的应对，胜率变化不大。"
        elif move_rate_change > 0:
            judge = f"这一手让{color_name}棋胜率提升了 {move_rate_change:.1f}%，是不错的选择！"
        else:
            judge = f"这一手让{color_name}棋胜率下降了 {-move_rate_change:.1f}%，可能是个疑问手。"
    else:
        judge = "开局阶段，双方棋力相当。"

    if abs(next_score_lead) < 5:
        tip = "局面比较平稳，双方接近均势。"
    else:
        leader = next_side_name if next_score_lead > 0 else ("白" if next_side == "B" else "黑")
        tip = f"局面已偏向{leader}棋，需要谨慎应对。"

    commentary = f"""第 {move_number} 手解析：

{color_name}方落子 {move['position'] if move else 'N/A'}。

【局势评估】
轮到{next_side_name}棋下，{next_side_name}棋胜率：{next_win_rate:.1f}%
目差（{next_side_name}棋视角）：{next_score_lead:+.1f} 目
{judge}

【KataGo 给{next_side_name}棋的推荐】
{rec_text}

【小贴士】
{tip}"""

    game["analyses"][move_number]["commentary"] = commentary.strip()
    return jsonify({"commentary": commentary.strip()})


@app.route("/api/engine/status", methods=["GET"])
def engine_status():
    return jsonify({
        "configured": is_katago_configured(),
        "config": config_store["katago"]
    })


@app.route("/api/engine/reset", methods=["POST"])
def engine_reset():
    reset_engine()
    reset_analysis_engine()
    return jsonify({"success": True})


def _moves_to_analysis_format(game_moves: List[Dict], up_to: int) -> List[List[str]]:
    """转换为 Analysis Engine 需要的格式 [["B", "Q16"], ["W", "D4"], ...]"""
    result = []
    for m in game_moves[:up_to]:
        color = "B" if m["color"] == "B" else "W"
        result.append([color, m["position"]])
    return result


@app.route("/api/flash-analyze/<game_id>", methods=["POST"])
def flash_analyze(game_id):
    """闪电分析：使用 KataGo Analysis Engine 一次性分析全局所有手"""
    game = _games_get(game_id)
    if game is None:
        return jsonify({"error": "Game not found"}), 404

    if not is_katago_configured():
        return jsonify({"error": "KataGo 未配置"}), 400
    data = request.json or {}
    max_visits = data.get("maxVisits", 100)
    turns_filter = data.get("turns")

    try:
        cfg = config_store["katago"]
        engine = get_analysis_engine(cfg["path"], cfg["configPath"], cfg["modelPath"])

        moves = _moves_to_analysis_format(game["moves"], len(game["moves"]))
        total = len(game["moves"])

        if turns_filter:
            analyze_turns = [t for t in turns_filter if 0 <= t <= total]
        else:
            analyze_turns = list(range(0, total + 1))

        is_human = "human" in (cfg["modelPath"] or "").lower()
        human_profile = "preaz_9d" if is_human else None

        print(f"[flash] 开始闪电分析: 共 {len(analyze_turns)} 个回合, maxVisits={max_visits}")
        results = engine.analyze_multi_turns(
            moves=moves,
            analyze_turns=analyze_turns,
            board_size=game["boardSize"],
            komi=game.get("komi", 6.5),
            max_visits=max_visits,
            humanSL_profile=human_profile,
            timeout=600
        )
        print(f"[flash] 收到 {len(results)} 个回合的结果")

        analyzed_count = 0
        for response in results:
            if "error" in response:
                print(f"[flash] 错误回合: {response.get('error')}")
                continue
            turn = response.get("turnNumber", -1)
            if turn < 0:
                continue
            parsed = parse_analysis_response(response)
            game["analyses"][turn] = {
                "moveNumber": turn,
                "winRate": parsed["winRate"],
                "scoreLead": parsed["scoreLead"],
                "recommendedMoves": parsed["recommendedMoves"],
                "totalVisits": parsed["totalVisits"],
                "isMock": False,
                "method": "flash"
            }
            analyzed_count += 1

        return jsonify({
            "success": True,
            "analyzed": analyzed_count,
            "total": len(analyze_turns),
            "analyses": game["analyses"]
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/hawk-eye/<game_id>", methods=["GET"])
def hawk_eye(game_id):
    """
    鹰眼分析：基于已有分析数据，计算每手的：
    - 吻合度 (matched): 实际下法是否在 KataGo 推荐前 N 手中
    - 胜率波动 (winRateChange): 与上一手胜率的差值
    - 目差波动 (scoreChange): 与上一手目差的差值
    - 失误等级 (errorLevel): excellent/good/normal/inaccuracy/mistake/blunder
    """
    game = _games_get(game_id)
    if game is None:
        return jsonify({"error": "Game not found"}), 404
    moves = game["moves"]
    analyses = game["analyses"]

    hawk_data = []
    prev_win_rate = None
    prev_score = None

    summary = {
        "blackBlunders": 0,
        "whiteBlunders": 0,
        "blackMistakes": 0,
        "whiteMistakes": 0,
        "blackInaccuracies": 0,
        "whiteInaccuracies": 0,
        "blackAccuracy": 0.0,
        "whiteAccuracy": 0.0,
        "blackMatchRate": 0.0,
        "whiteMatchRate": 0.0,
    }

    black_total = 0
    white_total = 0
    black_match = 0
    white_match = 0

    for i, move in enumerate(moves):
        move_num = i + 1

        actual_pos = move["position"]
        # 推荐手应来自落子前的局面分析 (move_num - 1)
        recommended = []
        prev_analysis = analyses.get(move_num - 1)
        if prev_analysis:
            recommended = [r["position"] for r in prev_analysis.get("recommendedMoves", [])]

        matched_rank = -1
        if recommended:
            try:
                matched_rank = recommended.index(actual_pos)
            except ValueError:
                matched_rank = -1

        is_match = 0 <= matched_rank < 5
        if move["color"] == "B":
            black_total += 1
            if is_match:
                black_match += 1
        else:
            white_total += 1
            if is_match:
                white_match += 1

        win_rate = None
        score_lead = None
        if move_num in analyses:
            win_rate = analyses[move_num].get("winRate")
            score_lead = analyses[move_num].get("scoreLead")

        win_rate_change = None
        score_change = None
        if win_rate is not None and prev_win_rate is not None:
            win_rate_change = round(win_rate - prev_win_rate, 2)
        if score_lead is not None and prev_score is not None:
            score_change = round(score_lead - prev_score, 2)

        # 失误等级判断（基于该手的胜率损失）
        # 黑棋下手：胜率下降 = 失误（因为下完后黑棋的胜率应该不变或增加）
        # 白棋下手：胜率上升 = 失误
        error_level = "normal"
        loss = 0.0
        if win_rate_change is not None:
            if move["color"] == "B":
                loss = -win_rate_change
            else:
                loss = win_rate_change

            if loss < -2:
                error_level = "excellent"
            elif loss < 1:
                error_level = "good"
            elif loss < 5:
                error_level = "normal"
            elif loss < 10:
                error_level = "inaccuracy"
                if move["color"] == "B":
                    summary["blackInaccuracies"] += 1
                else:
                    summary["whiteInaccuracies"] += 1
            elif loss < 20:
                error_level = "mistake"
                if move["color"] == "B":
                    summary["blackMistakes"] += 1
                else:
                    summary["whiteMistakes"] += 1
            else:
                error_level = "blunder"
                if move["color"] == "B":
                    summary["blackBlunders"] += 1
                else:
                    summary["whiteBlunders"] += 1

        hawk_data.append({
            "moveNumber": move_num,
            "color": move["color"],
            "position": actual_pos,
            "winRate": win_rate,
            "scoreLead": score_lead,
            "winRateChange": win_rate_change,
            "scoreChange": score_change,
            "matchedRank": matched_rank,
            "isMatch": is_match,
            "errorLevel": error_level,
            "loss": round(loss, 2)
        })

        if win_rate is not None:
            prev_win_rate = win_rate
        if score_lead is not None:
            prev_score = score_lead

    # 计算吻合率和准确度
    if black_total > 0:
        summary["blackMatchRate"] = round(black_match / black_total * 100, 1)
        bad_moves = summary["blackInaccuracies"] + summary["blackMistakes"] * 2 + summary["blackBlunders"] * 4
        summary["blackAccuracy"] = round(max(0, 100 - bad_moves / black_total * 100), 1)
    if white_total > 0:
        summary["whiteMatchRate"] = round(white_match / white_total * 100, 1)
        bad_moves = summary["whiteInaccuracies"] + summary["whiteMistakes"] * 2 + summary["whiteBlunders"] * 4
        summary["whiteAccuracy"] = round(max(0, 100 - bad_moves / white_total * 100), 1)

    return jsonify({
        "moves": hawk_data,
        "summary": summary,
        "totalMoves": len(moves),
        "analyzedMoves": len(analyses)
    })


@app.route("/api/estimate/<game_id>/<int:move_number>", methods=["GET"])
def estimate_territory(game_id, move_number):
    """形势判断 - 返回每个交叉点的归属概率"""
    game = _games_get(game_id)
    if game is None:
        return jsonify({"error": "Game not found"}), 404

    if not is_katago_configured():
        return jsonify({"error": "KataGo 未配置"}), 400

    try:
        cfg = config_store["katago"]
        engine = get_analysis_engine(cfg["path"], cfg["configPath"], cfg["modelPath"])

        is_human = "human" in (cfg["modelPath"] or "").lower()
        human_profile = "preaz_9d" if is_human else None

        moves = _moves_to_analysis_format(game["moves"], move_number)
        result = engine.estimate_territory(
            moves=moves,
            board_size=game["boardSize"],
            komi=game.get("komi", 6.5),
            max_visits=50,
            humanSL_profile=human_profile,
            timeout=30
        )

        ownership = result.get("ownership", [])
        return jsonify({
            "moveNumber": move_number,
            "ownership": ownership,
            "boardSize": game["boardSize"]
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/example-games", methods=["GET"])
def get_example_games():
    examples = [
        {
            "id": "example1",
            "name": "AlphaGo vs Lee Sedol - 第1局",
            "description": "2016年历史性对局"
        },
        {
            "id": "example2",
            "name": "柯洁 vs AlphaGo - 三番棋",
            "description": "2017年乌镇围棋峰会"
        }
    ]
    return jsonify(examples)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="go-reviewer backend server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("GO_REVIEWER_PORT", "5000")),
                        help="HTTP port to listen on (default: 5000 / env GO_REVIEWER_PORT)")
    parser.add_argument("--host", default=os.environ.get("GO_REVIEWER_HOST", "127.0.0.1"),
                        help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--prod", action="store_true",
                        help="Production mode (disable Flask debugger). Auto-on when frozen.")
    args = parser.parse_args()

    is_frozen = getattr(sys, "frozen", False)
    debug_mode = not (args.prod or is_frozen)

    # 关键: 打印一个 token 让 Tauri 主进程知道服务启动好了
    print(f"[ready] go-reviewer-backend listening on http://{args.host}:{args.port}", flush=True)

    app.run(host=args.host, port=args.port, debug=debug_mode, use_reloader=False, threaded=True)
