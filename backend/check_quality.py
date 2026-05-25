import urllib.request
import json

GAME_ID = "a26a54bf-feea-46b6-82b2-85084c5d9325"

print(f"=== 棋谱 {GAME_ID} ===")
res = urllib.request.urlopen(f"http://localhost:5000/api/game/{GAME_ID}")
game = json.loads(res.read())
print(f"总手数: {len(game['moves'])}")

print("\n=== 前 20 手 + 推荐 ===")
for move_num in range(1, 21):
    try:
        m = game['moves'][move_num - 1]
        res = urllib.request.urlopen(f"http://localhost:5000/api/analyze/{GAME_ID}/{move_num}")
        a = json.loads(res.read())
        is_mock = a.get('isMock', False)
        recs = a.get('recommendedMoves', [])
        rec_str = ", ".join(f"{r['position']}({r['visits']})" for r in recs[:3])
        print(f"  第{move_num:>2}手 {m['color']}{m['position']:>4} | 胜率 {a['winRate']:>5.1f}% | 目差 {a['scoreLead']:>+5.1f} | "
              f"{'[MOCK]' if is_mock else '[真实]'} 推荐: {rec_str}")
    except Exception as e:
        print(f"  第{move_num}手 错误: {e}")
