import os
from typing import Dict, Optional
from openai import AsyncOpenAI


class LLMClient:
    def __init__(self, api_key: str, base_url: Optional[str] = None, model: str = "gpt-4"):
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )

    async def generate_commentary(
        self,
        move_number: int,
        color: str,
        position: str,
        win_rate: Optional[float],
        score_lead: Optional[float],
        prev_win_rate: Optional[float],
        recommended_moves: list
    ) -> str:
        color_name = "黑" if color.upper() in ["B", "BLACK"] else "白"
        win_change = ""
        
        if prev_win_rate is not None and win_rate is not None:
            diff = win_rate - prev_win_rate
            if diff > 5:
                win_change = f"这手棋让黑棋胜率提升了约 {diff:.1f}%，是一步好棋！"
            elif diff < -5:
                win_change = f"这手棋让黑棋胜率下降了约 {-diff:.1f}%，需要注意。"
            else:
                win_change = f"这手棋后胜率变化不大（{diff:+.1f}%），属于正常的应对。"

        prompt = f"""你是一位经验丰富的围棋老师，擅长用通俗易懂的语言讲解棋局。请对以下这步棋进行解说：

第 {move_number} 手
{color_name}方下在 {position}
当前胜率：{win_rate:.1f}%（黑棋）
目差：{score_lead:+.1f} 目（黑领先为正）
{win_change}

推荐的其他走法：
{chr(10).join([f"- {m['position']}（胜率 {m['winRate']:.1f}%，访问次数 {m['visits']}）" for m in recommended_moves[:3]])}

请用中文，以亲切的老师口吻进行解说，包含以下内容：
1. 简要评价这步棋的质量（好棋/疑问手/正常应对）
2. 解释为什么这么下，可能的意图是什么
3. 如果有更好的选择，简单说明为什么推荐那些走法
4. 给初学者的建议或要点

请控制在 150-200 字，分点说明，但不要使用 markdown 格式。"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位经验丰富的围棋老师，擅长用通俗易懂的语言讲解棋局。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"AI 解说生成失败：{str(e)}"

    async def stream_commentary(
        self,
        move_number: int,
        color: str,
        position: str,
        win_rate: Optional[float],
        score_lead: Optional[float],
        prev_win_rate: Optional[float],
        recommended_moves: list
    ):
        color_name = "黑" if color.upper() in ["B", "BLACK"] else "白"
        win_change = ""
        
        if prev_win_rate is not None and win_rate is not None:
            diff = win_rate - prev_win_rate
            if diff > 5:
                win_change = f"这手棋让黑棋胜率提升了约 {diff:.1f}%，是一步好棋！"
            elif diff < -5:
                win_change = f"这手棋让黑棋胜率下降了约 {-diff:.1f}%，需要注意。"
            else:
                win_change = f"这手棋后胜率变化不大（{diff:+.1f}%），属于正常的应对。"

        prompt = f"""你是一位经验丰富的围棋老师，擅长用通俗易懂的语言讲解棋局。请对以下这步棋进行解说：

第 {move_number} 手
{color_name}方下在 {position}
当前胜率：{win_rate:.1f}%（黑棋）
目差：{score_lead:+.1f} 目（黑领先为正）
{win_change}

推荐的其他走法：
{chr(10).join([f"- {m['position']}（胜率 {m['winRate']:.1f}%，访问次数 {m['visits']}）" for m in recommended_moves[:3]])}

请用中文，以亲切的老师口吻进行解说，包含以下内容：
1. 简要评价这步棋的质量（好棋/疑问手/正常应对）
2. 解释为什么这么下，可能的意图是什么
3. 如果有更好的选择，简单说明为什么推荐那些走法
4. 给初学者的建议或要点

请控制在 150-200 字，分点说明，但不要使用 markdown 格式。"""

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位经验丰富的围棋老师，擅长用通俗易懂的语言讲解棋局。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500,
            stream=True
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
