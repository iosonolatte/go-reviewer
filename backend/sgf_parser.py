import re
from typing import List, Dict, Tuple, Optional


class SGFParser:
    LETTERS = "ABCDEFGHJKLMNOPQRST"

    @classmethod
    def parse(cls, sgf_content: str) -> Dict:
        result = {
            "moves": [],
            "boardSize": 19,
            "komi": 6.5,
            "playerBlack": "",
            "playerWhite": "",
            "result": ""
        }

        size_match = re.search(r"SZ\[(\d+)\]", sgf_content)
        if size_match:
            result["boardSize"] = int(size_match.group(1))

        komi_match = re.search(r"KM\[([^\]]+)\]", sgf_content)
        if komi_match:
            try:
                result["komi"] = float(komi_match.group(1))
            except:
                pass

        pb_match = re.search(r"PB\[([^\]]+)\]", sgf_content)
        if pb_match:
            result["playerBlack"] = pb_match.group(1)

        pw_match = re.search(r"PW\[([^\]]+)\]", sgf_content)
        if pw_match:
            result["playerWhite"] = pw_match.group(1)

        re_match = re.search(r"RE\[([^\]]+)\]", sgf_content)
        if re_match:
            result["result"] = re_match.group(1)

        move_pattern = r";([BW])\[([a-z]{2})\]"
        moves = re.findall(move_pattern, sgf_content)

        for idx, (color, pos) in enumerate(moves, 1):
            x = ord(pos[0]) - ord('a')
            y = ord(pos[1]) - ord('a')
            kata_pos = cls.sgf_to_kata(x, y, result["boardSize"])
            result["moves"].append({
                "number": idx,
                "color": color,
                "position": kata_pos,
                "sgfPos": pos,
                "x": x,
                "y": y
            })

        return result

    @classmethod
    def sgf_to_kata(cls, x: int, y: int, board_size: int = 19) -> str:
        if x < 0 or x >= board_size or y < 0 or y >= board_size:
            return ""
        return f"{cls.LETTERS[x]}{board_size - y}"

    @classmethod
    def kata_to_sgf(cls, kata_pos: str, board_size: int = 19) -> Tuple[int, int]:
        if not kata_pos or kata_pos.lower() == "pass":
            return (-1, -1)
        
        letter = kata_pos[0].upper()
        try:
            num = int(kata_pos[1:])
        except:
            return (-1, -1)
        
        x = cls.LETTERS.find(letter)
        y = board_size - num
        return (x, y)

    @classmethod
    def pos_to_coords(cls, kata_pos: str, board_size: int = 19, cell_size: int = 30) -> Tuple[int, int]:
        x, y = cls.kata_to_sgf(kata_pos, board_size)
        if x < 0:
            return (-1, -1)
        return (x * cell_size + cell_size // 2, y * cell_size + cell_size // 2)
