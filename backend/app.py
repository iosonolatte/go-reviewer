import os
import uuid
import json
import tempfile
import traceback
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

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), "go_reviewer_uploads")
try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except Exception:
    UPLOAD_FOLDER = tempfile.gettempdir()
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
print(f"[init] Upload folder: {UPLOAD_FOLDER}")

CONFIG_FILE = os.path.join(tempfile.gettempdir(), "go_reviewer_config.json")
print(f"[init] Config file: {CONFIG_FILE}")

games_store = {}
config_store = {
    "katago": {
        "path": "",
        "configPath": "",
        "modelPath": "",
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


def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_store, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[config] 保存配置失败: {e}")


load_config()


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


@app.route("/api/config/katago", methods=["POST"])
def set_katago_config():
    data = request.json
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
    config_store["llm"].update(data)
    save_config()
    return jsonify({"success": True, "config": config_store["llm"]})


@app.route("/api/config/llm", methods=["GET"])
def get_llm_config():
    return jsonify(config_store["llm"])


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
        games_store[game_id] = {
            "sgfContent": sgf_content,
            "moves": parsed["moves"],
            "boardSize": parsed["boardSize"],
            "komi": parsed["komi"],
            "playerBlack": parsed["playerBlack"],
            "playerWhite": parsed["playerWhite"],
            "result": parsed["result"],
            "analyses": {},
            "lastPlayedMove": 0
        }

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


@app.route("/api/game/new", methods=["POST"])
def create_new_game():
    """创建一个空白对局，用于实时落子模式"""
    data = request.json or {}
    board_size = int(data.get("boardSize", 19))
    komi = float(data.get("komi", 6.5))

    game_id = str(uuid.uuid4())
    games_store[game_id] = {
        "sgfContent": "",
        "moves": [],
        "boardSize": board_size,
        "komi": komi,
        "playerBlack": "黑方",
        "playerWhite": "白方",
        "result": "",
        "analyses": {},
        "lastPlayedMove": 0
    }

    return jsonify({
        "gameId": game_id,
        "moves": [],
        "boardSize": board_size,
        "komi": komi,
        "playerBlack": "黑方",
        "playerWhite": "白方",
        "result": ""
    })


@app.route("/api/game/<game_id>", methods=["GET"])
def get_game(game_id):
    if game_id not in games_store:
        return jsonify({"error": "Game not found"}), 404

    game = games_store[game_id]
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
    games_store[game_id] = {
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
    }
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
    if game_id not in games_store:
        return jsonify({"error": "Game not found"}), 404

    data = request.json or {}
    color = data.get("color")
    position = data.get("position")

    if color not in ("B", "W"):
        return jsonify({"error": "Invalid color"}), 400
    if not position:
        return jsonify({"error": "Missing position"}), 400

    game = games_store[game_id]

    # 把 KataGo 坐标 (如 Q16) 转回 (x,y)
    LETTERS = "ABCDEFGHJKLMNOPQRST"
    try:
        letter = position[0].upper()
        num = int(position[1:])
        x = LETTERS.index(letter)
        y = game["boardSize"] - num
    except (ValueError, IndexError):
        return jsonify({"error": f"Invalid position: {position}"}), 400

    move_num = len(game["moves"]) + 1
    game["moves"].append({
        "number": move_num,
        "color": color,
        "position": position,
        "x": x,
        "y": y
    })
    game["lastPlayedMove"] = move_num

    return jsonify({
        "success": True,
        "moveNumber": move_num,
        "moves": game["moves"]
    })


@app.route("/api/game/<game_id>/undo", methods=["POST"])
def undo_move(game_id):
    """实时落子：悔棋"""
    if game_id not in games_store:
        return jsonify({"error": "Game not found"}), 404

    game = games_store[game_id]
    if not game["moves"]:
        return jsonify({"error": "No moves to undo"}), 400

    removed = game["moves"].pop()
    game["lastPlayedMove"] = len(game["moves"])
    # 清除该手及之后的分析缓存
    move_num = removed.get("number", removed.get("moveNumber", 0))
    for k in list(game["analyses"].keys()):
        if k >= move_num:
            del game["analyses"][k]

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
    if game_id not in games_store:
        return jsonify({"error": "Game not found"}), 404

    game = games_store[game_id]

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
        # 1=超快(60), 3=快(120), 5=均衡(200), 10=精确(400), 20=深度(800)
        analyze_time = config_store["katago"].get("analyzeTime", 5)
        # 允许前端在 query 参数里临时覆盖
        override_visits = request.args.get("visits", type=int)
        if override_visits and override_visits > 0:
            max_visits = override_visits
        else:
            max_visits = max(60, min(2000, analyze_time * 40))

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
    if game_id not in games_store:
        return jsonify({"error": "Game not found"}), 404

    game = games_store[game_id]

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
    if game_id not in games_store:
        return jsonify({"error": "Game not found"}), 404

    if not is_katago_configured():
        return jsonify({"error": "KataGo 未配置"}), 400

    game = games_store[game_id]
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
    if game_id not in games_store:
        return jsonify({"error": "Game not found"}), 404

    game = games_store[game_id]
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
        analysis = analyses.get(move_num) or analyses.get(move_num - 1)

        actual_pos = move["position"]
        recommended = []
        if move_num - 1 in analyses:
            recommended = [r["position"] for r in analyses[move_num - 1].get("recommendedMoves", [])]
        elif analysis:
            recommended = [r["position"] for r in analysis.get("recommendedMoves", [])]

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
    if game_id not in games_store:
        return jsonify({"error": "Game not found"}), 404

    if not is_katago_configured():
        return jsonify({"error": "KataGo 未配置"}), 400

    game = games_store[game_id]

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
    app.run(debug=True, port=5000, use_reloader=False)
