import subprocess
import threading
import queue
import re
import time
from typing import List, Dict, Optional


class KataGoEngine:
    """
    持久化的 KataGo GTP 引擎封装。
    一次启动后可重复使用，避免反复加载模型。
    """

    def __init__(self, katago_path: str, config_path: str, model_path: str):
        self.katago_path = katago_path
        self.config_path = config_path
        self.model_path = model_path
        self.process: Optional[subprocess.Popen] = None
        self.stdout_queue: queue.Queue = queue.Queue()
        self.stderr_lines: List[str] = []
        self._lock = threading.Lock()
        self._running = False

    def start(self):
        if self.process is not None:
            return

        # 自动选择 GTP 兼容的配置
        gtp_config_path = self.config_path
        try:
            with open(self.config_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if "numAnalysisThreads" in content and "numSearchThreads" not in content.replace("numAnalysisThreads", ""):
                # 这是 analysis 配置，需要找 GTP 配置
                import os as _os
                katago_dir = _os.path.dirname(self.katago_path)
                candidates = [
                    _os.path.join(katago_dir, "default_gtp.cfg"),
                    _os.path.join(katago_dir, "gtp_example.cfg"),
                    _os.path.join(_os.path.dirname(self.config_path), "default_gtp.cfg"),
                ]
                for c in candidates:
                    if _os.path.exists(c):
                        print(f"[engine] 自动切换到 GTP 配置: {c}")
                        gtp_config_path = c
                        break
        except Exception:
            pass

        print(f"[engine] 正在启动 KataGo (GTP): {self.katago_path}")
        print(f"[engine] 配置文件: {gtp_config_path}")
        print(f"[engine] 权重文件: {self.model_path}")

        self.process = subprocess.Popen(
            [
                self.katago_path, "gtp",
                "-config", gtp_config_path,
                "-model", self.model_path
            ],
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

        ready = self._wait_ready(timeout=600)
        if not ready:
            stderr_tail = self.stderr_lines[-20:] if self.stderr_lines else ["(无输出)"]
            print("[engine] 启动失败，最后 stderr 输出:")
            for line in stderr_tail:
                try:
                    safe_line = line.rstrip().encode("ascii", errors="replace").decode("ascii")
                    print(f"  {safe_line}")
                except Exception:
                    pass
            if self.process.poll() is not None:
                print(f"[engine] 进程已退出，退出码: {self.process.poll()}")
            else:
                print("[engine] 进程仍在运行，但未响应 GTP 命令")
            raise RuntimeError(
                "KataGo 引擎启动超时。"
                "请检查：1) 路径是否正确 2) 配置文件是否有效 3) GPU 驱动是否正常"
            )
        print("[engine] KataGo 引擎启动成功！")

        # 检查是否是 human 模型，如果是则设置默认人类等级
        is_human_model = "human" in (self.model_path or "").lower()
        if is_human_model:
            print("[engine] 检测到 human 模型，正在设置 humanSLProfile...")
            try:
                # 尝试设置默认的人类棋力等级
                resp = self._send("kata-set-param humanSLProfile preaz_9d", timeout=10)
                if resp.startswith("?"):
                    # 命令失败，尝试其他参数名
                    resp = self._send("kata-set-rules japanese", timeout=5)
                print(f"[engine] humanSLProfile 设置响应: {resp.strip()[:200]}")
            except Exception as e:
                print(f"[engine] 设置 humanSLProfile 失败: {e}")

    def _read_stdout(self):
        while self._running and self.process and self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                self.stdout_queue.put(line)
            except Exception:
                break

    def _read_stderr(self):
        while self._running and self.process and self.process.stderr:
            try:
                line = self.process.stderr.readline()
                if not line:
                    break
                self.stderr_lines.append(line)
                if len(self.stderr_lines) > 200:
                    self.stderr_lines.pop(0)
            except Exception:
                break

    def _wait_ready(self, timeout: int = 120) -> bool:
        """等待 KataGo 就绪。先等待 stderr 出现 'GTP ready' 再发送 GTP 命令验证。"""
        # 等待 stderr 中出现 GTP ready 标志
        gtp_ready_deadline = time.time() + timeout
        gtp_ready = False
        while time.time() < gtp_ready_deadline:
            for line in self.stderr_lines[-50:]:
                if "GTP ready" in line:
                    gtp_ready = True
                    break
            if gtp_ready:
                break
            if self.process.poll() is not None:
                print(f"[engine] 进程已退出，退出码: {self.process.poll()}")
                return False
            time.sleep(0.5)

        if not gtp_ready:
            print("[engine] 等待 GTP ready 超时")
            return False

        print("[engine] 检测到 GTP ready，发送测试命令...")

        # 清空已有响应
        self._drain()

        try:
            self.process.stdin.write("name\n")
            self.process.stdin.flush()
        except Exception as e:
            print(f"[engine] 发送命令失败: {e}")
            return False

        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                line = self.stdout_queue.get(timeout=1)
                if line.startswith("="):
                    self._drain()
                    return True
            except queue.Empty:
                if self.process.poll() is not None:
                    return False
        return False

    def _drain(self):
        while True:
            try:
                self.stdout_queue.get_nowait()
            except queue.Empty:
                break

    def _send(self, cmd: str, timeout: int = 60) -> str:
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError("KataGo 引擎未运行")

        with self._lock:
            self._drain()
            self.process.stdin.write(cmd + "\n")
            self.process.stdin.flush()

            lines: List[str] = []
            deadline = time.time() + timeout
            got_response = False
            while time.time() < deadline:
                try:
                    line = self.stdout_queue.get(timeout=1)
                except queue.Empty:
                    continue

                if not got_response:
                    if line.startswith("=") or line.startswith("?"):
                        got_response = True
                        lines.append(line)
                else:
                    if line.strip() == "":
                        break
                    lines.append(line)

            return "".join(lines)

    def clear_board(self):
        return self._send("clear_board")

    def boardsize(self, size: int = 19):
        return self._send(f"boardsize {size}")

    def komi(self, komi: float = 6.5):
        return self._send(f"komi {komi}")

    def play(self, color: str, position: str):
        return self._send(f"play {color} {position}")

    def analyze(self, color: str, analyze_seconds: int = 5) -> Dict:
        """
        使用 kata-analyze 进行一次分析。
        analyze_seconds: 分析持续时间（秒），决定 visits 数量
        返回胜率、目差、推荐走法。
        """
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError("KataGo 引擎未运行")

        with self._lock:
            self._drain()
            # interval 单位是 1/100 秒，1000 = 10 秒一次刷新
            cmd = f"kata-analyze {color} interval 100 maxmoves 10\n"
            self.process.stdin.write(cmd)
            self.process.stdin.flush()

            best_info_line = ""
            # 等待 analyze_seconds 秒收集 KataGo 的分析结果
            # 在此期间一直读取最新的 info 行（覆盖旧的）
            deadline = time.time() + analyze_seconds
            no_data_count = 0

            while time.time() < deadline:
                try:
                    line = self.stdout_queue.get(timeout=0.5)
                    no_data_count = 0
                    if line.startswith("info"):
                        best_info_line = line
                except queue.Empty:
                    no_data_count += 1
                    # 如果一直没数据，可能引擎崩溃了
                    if no_data_count > 20 and not best_info_line:
                        break
                    continue

            # 停止分析（发送一个空命令打断 kata-analyze）
            try:
                self.process.stdin.write("name\n")
                self.process.stdin.flush()
            except Exception:
                pass

            # 给一点时间让停止生效
            time.sleep(0.3)

            # 再读取一些数据，找到最新的 info 行
            extra_deadline = time.time() + 1
            while time.time() < extra_deadline:
                try:
                    line = self.stdout_queue.get(timeout=0.2)
                    if line.startswith("info"):
                        best_info_line = line
                except queue.Empty:
                    break

            # 清空响应队列
            self._drain()

            return self._parse_analyze_line(best_info_line)

    @staticmethod
    def _parse_analyze_line(line: str) -> Dict:
        result = {
            "winRate": None,
            "scoreLead": None,
            "recommendedMoves": []
        }
        if not line:
            return result

        # kata-analyze 输出格式：
        # info move D4 visits 100 winrate 0.512 scoreLead 0.5 ... pv D4 Q16 ...
        # info move ...
        moves_info = re.split(r"\binfo\s+move\s+", line)
        for chunk in moves_info:
            chunk = chunk.strip()
            if not chunk:
                continue
            parts = chunk.split()
            if not parts:
                continue
            position = parts[0]
            visits = 0
            winrate = 0.0
            score_lead = 0.0
            i = 1
            while i < len(parts) - 1:
                key = parts[i]
                val = parts[i + 1]
                if key == "visits":
                    try:
                        visits = int(val)
                    except ValueError:
                        pass
                elif key == "winrate":
                    try:
                        winrate = float(val) * 100
                    except ValueError:
                        pass
                elif key == "scoreLead":
                    try:
                        score_lead = float(val)
                    except ValueError:
                        pass
                elif key == "pv":
                    break
                i += 1

            result["recommendedMoves"].append({
                "position": position,
                "visits": visits,
                "winRate": round(winrate, 2)
            })

            if result["winRate"] is None:
                result["winRate"] = round(winrate, 2)
                result["scoreLead"] = round(score_lead, 2)

        result["recommendedMoves"].sort(key=lambda m: m["visits"], reverse=True)
        result["recommendedMoves"] = result["recommendedMoves"][:5]
        return result

    def stop(self):
        self._running = False
        if self.process:
            try:
                if self.process.stdin and not self.process.stdin.closed:
                    try:
                        self.process.stdin.write("quit\n")
                        self.process.stdin.flush()
                    except (OSError, ValueError):
                        pass
            except Exception:
                pass
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None


_engine_instance: Optional[KataGoEngine] = None
_engine_lock = threading.Lock()


def get_engine(katago_path: str, config_path: str, model_path: str) -> KataGoEngine:
    """获取或重建持久化引擎实例。"""
    global _engine_instance
    with _engine_lock:
        if (_engine_instance is None
                or _engine_instance.katago_path != katago_path
                or _engine_instance.config_path != config_path
                or _engine_instance.model_path != model_path
                or (_engine_instance.process and _engine_instance.process.poll() is not None)):
            if _engine_instance is not None:
                try:
                    _engine_instance.stop()
                except Exception:
                    pass
            _engine_instance = KataGoEngine(katago_path, config_path, model_path)
            _engine_instance.start()
        return _engine_instance


def reset_engine():
    global _engine_instance
    with _engine_lock:
        if _engine_instance is not None:
            try:
                _engine_instance.stop()
            except Exception:
                pass
            _engine_instance = None
