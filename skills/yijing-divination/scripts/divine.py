#!/usr/bin/env python3
"""
易经占卜脚本 - 卦象生成
支持铜钱法和蓍草法模拟
"""
import random
import sys
import json
from datetime import datetime

# 卦象名称映射（二进制 → 八卦）
TRIGRAMS = {
    0b111: {"name": "乾", "symbol": "☰", "element": "天", "attribute": "刚健"},
    0b110: {"name": "兑", "symbol": "☱", "element": "泽", "attribute": "喜悦"},
    0b101: {"name": "离", "symbol": "☲", "element": "火", "attribute": "附丽"},
    0b100: {"name": "震", "symbol": "☳", "element": "雷", "attribute": "奋进"},
    0b011: {"name": "巽", "symbol": "☴", "element": "风", "attribute": "谦逊"},
    0b010: {"name": "坎", "symbol": "☵", "element": "水", "attribute": "险陷"},
    0b001: {"name": "艮", "symbol": "☶", "element": "山", "attribute": "止静"},
    0b000: {"name": "坤", "symbol": "☷", "element": "地", "attribute": "柔顺"},
}

# 六十四卦序号映射（上卦×8 + 下卦）
HEXAGRAM_ORDER = {
    0o77: 1, 0o76: 43, 0o75: 14, 0o74: 34, 0o73: 9, 0o72: 5, 0o71: 26, 0o70: 11,
    0o67: 10, 0o66: 58, 0o65: 38, 0o64: 54, 0o63: 61, 0o62: 60, 0o61: 41, 0o60: 19,
    0o57: 13, 0o56: 49, 0o55: 30, 0o54: 55, 0o53: 37, 0o52: 63, 0o51: 22, 0o50: 36,
    0o47: 25, 0o46: 17, 0o45: 21, 0o44: 51, 0o43: 42, 0o42: 3, 0o41: 27, 0o40: 24,
    0o37: 44, 0o36: 28, 0o35: 50, 0o34: 32, 0o33: 57, 0o32: 48, 0o31: 18, 0o30: 46,
    0o27: 6, 0o26: 47, 0o25: 64, 0o24: 40, 0o23: 59, 0o22: 29, 0o21: 4, 0o20: 7,
    0o17: 33, 0o16: 31, 0o15: 56, 0o14: 62, 0o13: 53, 0o12: 39, 0o11: 52, 0o10: 15,
    0o07: 12, 0o06: 45, 0o05: 35, 0o04: 16, 0o03: 20, 0o02: 8, 0o01: 23, 0o00: 2,
}


def coin_method(seed=None):
    """铜钱法：三枚铜钱投掷六次"""
    if seed:
        random.seed(seed)
    
    lines = []
    changing_lines = []
    
    for i in range(6):
        # 三枚铜钱：正面=3，反面=2
        # 总和：6(老阴)、7(少阳)、8(少阴)、9(老阳)
        coins = [random.choice([2, 3]) for _ in range(3)]
        total = sum(coins)
        
        if total == 6:  # 老阴 → 阴爻变阳
            lines.append(0)
            changing_lines.append(i + 1)
        elif total == 7:  # 少阳 → 阳爻不变
            lines.append(1)
        elif total == 8:  # 少阴 → 阴爻不变
            lines.append(0)
        elif total == 9:  # 老阳 → 阳爻变阴
            lines.append(1)
            changing_lines.append(i + 1)
    
    return lines, changing_lines


def yarrow_method(seed=None):
    """蓍草法：大衍之数模拟（简化版）"""
    if seed:
        random.seed(seed)
    
    lines = []
    changing_lines = []
    
    for i in range(6):
        # 简化的蓍草法：三变过程
        # 实际蓍草法更复杂，这里模拟概率分布
        # 老阳(9): 1/16, 少阳(7): 7/16, 少阴(8): 7/16, 老阴(6): 1/16
        weights = [1, 7, 7, 1]
        result = random.choices([9, 7, 8, 6], weights=weights)[0]
        
        if result == 6:  # 老阴
            lines.append(0)
            changing_lines.append(i + 1)
        elif result == 7:  # 少阳
            lines.append(1)
        elif result == 8:  # 少阴
            lines.append(0)
        elif result == 9:  # 老阳
            lines.append(1)
            changing_lines.append(i + 1)
    
    return lines, changing_lines


def lines_to_hexagram(lines):
    """六爻 → 卦象编号"""
    # 下卦（初爻到三爻）
    lower = (lines[0] << 0) | (lines[1] << 1) | (lines[2] << 2)
    # 上卦（四爻到上爻）
    upper = (lines[3] << 0) | (lines[4] << 1) | (lines[5] << 2)
    
    # 八进制编码
    code = (upper << 3) | lower
    return HEXAGRAM_ORDER.get(code, 0)


def calculate_relating_hexagram(lines, changing_lines):
    """计算变卦（之卦）"""
    if not changing_lines:
        return None
    
    new_lines = lines.copy()
    for pos in changing_lines:
        idx = pos - 1
        new_lines[idx] = 1 - new_lines[idx]  # 阴变阳，阳变阴
    
    return lines_to_hexagram(new_lines)


def calculate_nuclear_hexagram(lines):
    """计算互卦（2-4爻为下卦，3-5爻为上卦）"""
    lower = (lines[1] << 0) | (lines[2] << 1) | (lines[3] << 2)
    upper = (lines[2] << 0) | (lines[3] << 1) | (lines[4] << 2)
    code = (upper << 3) | lower
    return HEXAGRAM_ORDER.get(code, 0)


def format_hexagram_visual(lines, changing_lines):
    """可视化卦象"""
    visual = []
    line_names = ["上爻", "五爻", "四爻", "三爻", "二爻", "初爻"]
    
    for i in range(5, -1, -1):
        line_num = i + 1
        is_changing = line_num in changing_lines
        
        if lines[i] == 1:  # 阳爻
            symbol = "━━━━━━" if not is_changing else "━━━━━━ ○"
        else:  # 阴爻
            symbol = "━━  ━━" if not is_changing else "━━  ━━ ×"
        
        visual.append(f"{line_names[5-i]}: {symbol}")
    
    return "\n".join(visual)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="易经占卜 - 卦象生成")
    parser.add_argument("--method", choices=["coin", "yarrow"], default="coin",
                        help="起卦方法：coin(铜钱法) 或 yarrow(蓍草法)")
    parser.add_argument("--seed", type=str, help="随机种子（可用时间戳或问题文本）")
    parser.add_argument("--question", type=str, help="问卦问题（可选）")
    
    args = parser.parse_args()
    
    # 使用问题文本作为种子
    seed = args.seed or (hash(args.question) if args.question else None)
    
    # 起卦
    if args.method == "coin":
        lines, changing_lines = coin_method(seed)
    else:
        lines, changing_lines = yarrow_method(seed)
    
    # 计算卦象
    main_hex = lines_to_hexagram(lines)
    nuclear_hex = calculate_nuclear_hexagram(lines)
    relating_hex = calculate_relating_hexagram(lines, changing_lines)
    
    # 上下卦
    lower_trigram_code = (lines[0] << 0) | (lines[1] << 1) | (lines[2] << 2)
    upper_trigram_code = (lines[3] << 0) | (lines[4] << 1) | (lines[5] << 2)
    lower_trigram = TRIGRAMS[lower_trigram_code]
    upper_trigram = TRIGRAMS[upper_trigram_code]
    
    # 输出结果
    result = {
        "timestamp": datetime.now().isoformat(),
        "method": args.method,
        "question": args.question,
        "main_hexagram": {
            "number": main_hex,
            "upper_trigram": upper_trigram,
            "lower_trigram": lower_trigram,
            "lines": lines,
            "changing_lines": changing_lines,
            "visual": format_hexagram_visual(lines, changing_lines)
        },
        "nuclear_hexagram": nuclear_hex,
        "relating_hexagram": relating_hex
    }
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
