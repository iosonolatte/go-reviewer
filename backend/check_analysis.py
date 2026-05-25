import urllib.request
import json

game_id = "c40b7ff6-617c-46c0-820d-10e976cac973"

print("=== 棋谱信息 ===")
res = urllib.request.urlopen(f"http://localhost:5000/api/game/{game_id}")
game = json.loads(res.read())
print(f"总手数: {len(game['moves'])}")
print(f"前 10 手:")
for m in game['moves'][:10]:
    print(f"  {m['number']}. {m['color']} {m['position']} (x={m['x']}, y={m['y']})")

print("\n=== 分析结果对比 ===")
for move_num in [5, 6]:
    try:
        res = urllib.request.urlopen(f"http://localhost:5000/api/analyze/{game_id}/{move_num}")
        analysis = json.loads(res.read())
        print(f"\n第 {move_num} 手:")
        print(f"  isMock: {analysis.get('isMock', 'N/A')}")
        print(f"  胜率: {analysis['winRate']}%")
        print(f"  目差: {analysis['scoreLead']}")
        print(f"  推荐数: {len(analysis['recommendedMoves'])}")
        for i, rm in enumerate(analysis['recommendedMoves'][:3], 1):
            print(f"    {i}. {rm['position']} 胜率 {rm['winRate']}% 访问 {rm['visits']}")
    except Exception as e:
        print(f"第 {move_num} 手错误: {e}")
