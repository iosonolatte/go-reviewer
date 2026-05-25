"""
KataGo Analysis Engine 封装。
使用 KataGo 的 'analysis' 模式（JSON 通信），相比 GTP 模式有以下优势：
- 支持批量并发查询（一次请求分析多手）
- 速度更快（不需要逐手 play）
- 输出为结构化 JSON（不需要解析）
- 适合做闪电分析、批量复盘
"""
import os
import subprocess
import threading
import queue
import json
import time
import uuid
import tempfile
from typing import Dict, List, Optional


def _ensure_analysis_config(katago_dir: str, user_config_path: str) -> str:
    """
    确保有一个 Analysis Engine 可以使用的配置文件。
    优先级：
    1) 同目录或用户配置目录的 analysis_fast.cfg（速度优化版，最高优先级）
    2) 用户配置已是 analysis 配置（含 numAnalysisThreads）
    3) 同目录的 analysis_example.cfg
    4) 自动生成的临时配置
    """
    # 1) 优先使用速度优化版配置（如果存在）
    fast_candidates = [
        os.path.join(katago_dir, "analysis_fast.cfg"),
        os.path.join(os.path.dirname(user_config_path), "analysis_fast.cfg"),
    ]
    for c in fast_candidates:
        if os.path.exists(c):
            print(f"[analysis-engine] 使用速度优化配置: {c}")
            return c

    # 2) 用户配置如果就是 analysis 配置（含 numAnalysisThreads），直接用
    try:
        with open(user_config_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        if "numAnalysisThreads" in content:
            print(f"[analysis-engine] 使用用户配置: {user_config_path}")
            return user_config_path
    except Exception:
        pass

    # 3) 尝试找同目录下的 analysis_example.cfg
    candidates = [
        os.path.join(katago_dir, "analysis_example.cfg"),
        os.path.join(os.path.dirname(user_config_path), "analysis_example.cfg"),
    ]
    for c in candidates:
        if os.path.exists(c):
            print(f"[analysis-engine] 使用 analysis_example 配置: {c}")
            return c

    # 4) 兜底：生成一个最简的临时配置
    tmp_config = os.path.join(tempfile.gettempdir(), "go_reviewer_analysis.cfg")
    with open(tmp_config, "w", encoding="utf-8") as f:
        f.write(
            "logToStderr = true\n"
            "logAllRequests = false\n"
            "logAllResponses = false\n"
            "logSearchInfo = false\n"
            "reportAnalysisWinratesAs = BLACK\n"
            "numAnalysisThreads = 2\n"
            "numSearchThreadsPerAnalysisThread = 16\n"
            "maxVisits = 200\n"
            "nnMaxBatchSize = 16\n"
            "rules = tromp-taylor\n"
        )
    print(f"[analysis-engine] 自动生成临时配置: {tmp_config}")
    return tmp_config


class KataGoAnalysisEngine:
    def __init__(self, katago_path: str, config_path: str, model_path: str,
                 analysis_threads: int = 4):
        self.katago_path = katago_path
        self.config_path = config_path
        self.model_path = model_path
        self.analysis_threads = analysis_threads
        self.process: Optional[subprocess.Popen] = None
        self._response_queue: queue.Queue = queue.Queue()
        self._stderr_lines: List[str] = []
        self._pending: Dict[str, queue.Queue] = {}
        self._lock = threading.Lock()
        self._running = False

    def start(self) -> bool:
        if self.process is not None:
            return True

        # 自动选择 Analysis Engine 兼容的配置
        katago_dir = os.path.dirname(self.katago_path)
        analysis_config = _ensure_analysis_config(katago_dir, self.config_path)

        # 检查配置中是否已经有 numAnalysisThreads，如果没有才添加 -analysis-threads
        try:
            with open(analysis_config, "r", encoding="utf-8", errors="ignore") as f:
                cfg_content = f.read()
            has_num_threads = "numAnalysisThreads" in cfg_content and not all(
                line.strip().startswith("#")
                for line in cfg_content.split("\n")
                if "numAnalysisThreads" in line
            )
        except Exception:
            has_num_threads = False

        cmd = [
            self.katago_path, "analysis",
            "-config", analysis_config,
            "-model", self.model_path,
        ]
        if not has_num_threads:
            cmd.extend(["-analysis-threads", str(self.analysis_threads)])

        print(f"[analysis-engine] starting...")
        print(f"  cmd: {' '.join(cmd)}")

        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace"
        )
        self._running = True
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

        deadline = time.time() + 600
        while time.time() < deadline:
            for line in self._stderr_lines[-100:]:
                if "Started, ready to begin handling requests" in line:
                    print("[analysis-engine] OK - engine ready")
                    return True
            if self.process.poll() is not None:
                print(f"[analysis-engine] FAIL - process exited (code={self.process.poll()})")
                # 打印最后的 stderr 输出帮助诊断
                tail = self._stderr_lines[-30:]
                print("[analysis-engine] last stderr lines:")
                for line in tail:
                    try:
                        safe = line.rstrip().encode("ascii", errors="replace").decode("ascii")
                        print(f"  {safe}")
                    except Exception:
                        pass
                return False
            time.sleep(0.5)

        print("[analysis-engine] FAIL - startup timeout")
        return False

    def _read_stdout(self):
        while self._running and self.process and self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    req_id = data.get("id")
                    if req_id and req_id in self._pending:
                        self._pending[req_id].put(data)
                    else:
                        self._response_queue.put(data)
                except json.JSONDecodeError:
                    pass
            except Exception:
                break

    def _read_stderr(self):
        while self._running and self.process and self.process.stderr:
            try:
                line = self.process.stderr.readline()
                if not line:
                    break
                self._stderr_lines.append(line)
                if len(self._stderr_lines) > 500:
                    self._stderr_lines.pop(0)
            except Exception:
                break

    def analyze_position(
        self,
        moves: List[List[str]],
        board_size: int = 19,
        komi: float = 6.5,
        max_visits: int = 200,
        rules: str = "tromp-taylor",
        timeout: int = 60,
        humanSL_profile: Optional[str] = None,
        analyze_turn: Optional[int] = None
    ) -> Dict:
        """
        分析一个局面，返回 KataGo 的分析结果。
        moves: [["B", "Q16"], ["W", "D4"], ...]
        analyze_turn: 要分析的回合数（默认是棋谱最后一手之后）
        """
        req_id = str(uuid.uuid4())
        if analyze_turn is None:
            analyze_turn = len(moves)

        request = {
            "id": req_id,
            "moves": moves,
            "rules": rules,
            "komi": komi,
            "boardXSize": board_size,
            "boardYSize": board_size,
            "analyzeTurns": [analyze_turn],
            "maxVisits": max_visits,
            "includeOwnership": False,
            "includePolicy": False,
            "includePVVisits": False
        }
        if humanSL_profile:
            request["overrideSettings"] = {
                "humanSLProfile": humanSL_profile
            }

        return self._send_request(req_id, request, timeout)

    def analyze_multi_turns(
        self,
        moves: List[List[str]],
        analyze_turns: List[int],
        board_size: int = 19,
        komi: float = 6.5,
        max_visits: int = 200,
        rules: str = "tromp-taylor",
        timeout: int = 600,
        humanSL_profile: Optional[str] = None
    ) -> List[Dict]:
        """一次性分析多个回合 - 闪电分析的核心"""
        req_id = str(uuid.uuid4())
        request = {
            "id": req_id,
            "moves": moves,
            "rules": rules,
            "komi": komi,
            "boardXSize": board_size,
            "boardYSize": board_size,
            "analyzeTurns": analyze_turns,
            "maxVisits": max_visits,
            "includeOwnership": False,
            "includePolicy": False
        }
        if humanSL_profile:
            request["overrideSettings"] = {
                "humanSLProfile": humanSL_profile
            }

        return self._send_request_multi(req_id, request, len(analyze_turns), timeout)

    def estimate_territory(
        self,
        moves: List[List[str]],
        board_size: int = 19,
        komi: float = 6.5,
        max_visits: int = 50,
        rules: str = "tromp-taylor",
        timeout: int = 30,
        humanSL_profile: Optional[str] = None
    ) -> Dict:
        """形势判断 - 返回 ownership 信息"""
        req_id = str(uuid.uuid4())
        request = {
            "id": req_id,
            "moves": moves,
            "rules": rules,
            "komi": komi,
            "boardXSize": board_size,
            "boardYSize": board_size,
            "analyzeTurns": [len(moves)],
            "maxVisits": max_visits,
            "includeOwnership": True
        }
        if humanSL_profile:
            request["overrideSettings"] = {
                "humanSLProfile": humanSL_profile
            }
        return self._send_request(req_id, request, timeout)

    def _send_request(self, req_id: str, request: Dict, timeout: int) -> Dict:
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError("Analysis 引擎未运行")

        q: queue.Queue = queue.Queue()
        self._pending[req_id] = q

        try:
            with self._lock:
                self.process.stdin.write(json.dumps(request) + "\n")
                self.process.stdin.flush()

            try:
                response = q.get(timeout=timeout)
                return response
            except queue.Empty:
                raise RuntimeError(f"Analysis 请求超时 ({timeout}s)")
        finally:
            self._pending.pop(req_id, None)

    def _send_request_multi(self, req_id: str, request: Dict, expected: int, timeout: int) -> List[Dict]:
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError("Analysis 引擎未运行")

        q: queue.Queue = queue.Queue()
        self._pending[req_id] = q

        results = []
        try:
            with self._lock:
                self.process.stdin.write(json.dumps(request) + "\n")
                self.process.stdin.flush()

            deadline = time.time() + timeout
            while len(results) < expected and time.time() < deadline:
                try:
                    response = q.get(timeout=min(30, deadline - time.time()))
                    results.append(response)
                    if response.get("isDuringSearch") is False:
                        # 包含 isDuringSearch=false 表示这一回合的最终结果
                        pass
                except queue.Empty:
                    break

            return results
        finally:
            self._pending.pop(req_id, None)

    def stop(self):
        self._running = False
        if self.process:
            try:
                self.process.stdin.write(json.dumps({"action": "terminate_all"}) + "\n")
                self.process.stdin.flush()
            except Exception:
                pass
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None


_analysis_engine: Optional[KataGoAnalysisEngine] = None
_analysis_lock = threading.Lock()


def get_analysis_engine(katago_path: str, config_path: str, model_path: str) -> KataGoAnalysisEngine:
    global _analysis_engine
    with _analysis_lock:
        if (_analysis_engine is None
                or _analysis_engine.katago_path != katago_path
                or _analysis_engine.config_path != config_path
                or _analysis_engine.model_path != model_path
                or (_analysis_engine.process and _analysis_engine.process.poll() is not None)):
            if _analysis_engine is not None:
                try:
                    _analysis_engine.stop()
                except Exception:
                    pass
            _analysis_engine = KataGoAnalysisEngine(katago_path, config_path, model_path)
            ok = _analysis_engine.start()
            if not ok:
                _analysis_engine = None
                raise RuntimeError("Analysis 引擎启动失败")
        return _analysis_engine


def reset_analysis_engine():
    global _analysis_engine
    with _analysis_lock:
        if _analysis_engine is not None:
            try:
                _analysis_engine.stop()
            except Exception:
                pass
            _analysis_engine = None


def parse_analysis_response(response: Dict) -> Dict:
    """将 KataGo Analysis Engine 的响应转换为统一格式"""
    root_info = response.get("rootInfo", {})
    move_infos = response.get("moveInfos", [])

    win_rate = root_info.get("winrate", 0.5) * 100
    score_lead = root_info.get("scoreLead", 0)
    visits = root_info.get("visits", 0)

    recommended = []
    for mi in move_infos[:10]:
        recommended.append({
            "position": mi.get("move", ""),
            "winRate": round(mi.get("winrate", 0.5) * 100, 2),
            "scoreLead": round(mi.get("scoreLead", 0), 2),
            "visits": mi.get("visits", 0),
            "prior": round(mi.get("prior", 0) * 100, 2),
            "order": mi.get("order", 0)
        })

    return {
        "winRate": round(win_rate, 2),
        "scoreLead": round(score_lead, 2),
        "totalVisits": visits,
        "recommendedMoves": recommended,
        "turnNumber": response.get("turnNumber", 0)
    }
