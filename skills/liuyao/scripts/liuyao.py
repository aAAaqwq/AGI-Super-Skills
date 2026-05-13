#!/usr/bin/env python3
"""
六爻起卦脚本 - 纯Python无依赖版本
直接在Ubuntu/Linux终端运行
"""

import random


def toss_three_coins():
    """模拟掷三枚硬币"""
    coins = [random.randint(0, 1) for _ in range(3)]
    total = sum(coins)
    is_moving = False
    line_char = ""
    line_name = ""

    if total == 3:
        # 3阳：老阳（动爻）
        line_name = "老阳(动)"
        line_char = "—"
        is_moving = True
    elif total == 0:
        # 3阴：老阴（动爻）
        line_name = "老阴(动)"
        line_char = "--"
        is_moving = True
    elif total == 2:
        # 2阳1阴：少阴（静爻）
        line_name = "少阴"
        line_char = "--"
    else:
        # 1阳2阴：少阳（静爻）
        line_name = "少阳"
        line_char = "—"

    return total, line_name, line_char, is_moving


def generate_changed_line(original_char: str, is_moving: bool) -> str:
    """生成变卦的爻"""
    if not is_moving:
        return original_char
    return "--" if original_char == "—" else "—"


def main():
    print("=" * 50)
    print("  🔮 六爻起卦 - Liuyao Divination")
    print("=" * 50)
    print("规则：掷3枚硬币 x 6次 = 1个卦象\n")

    original_lines = []
    changed_lines = []
    moving_line_indices = []

    # 掷6次，从下往上
    for i in range(1, 7):
        total, name, char, moving = toss_three_coins()
        original_lines.append(char)
        changed_char = generate_changed_line(char, moving)
        changed_lines.append(changed_char)

        if moving:
            moving_line_indices.append(str(i))

        print(f"第{i}爻：{char} | {name}")

    # 反转显示（传统格式：上卦在上）
    original_display = list(reversed(original_lines))
    changed_display = list(reversed(changed_lines))

    print("\n" + "-" * 50)
    print("【本卦】(上爻在前)")
    for idx, line in enumerate(original_display):
        print(f" 第{6-idx}爻：{line}")

    print("\n【变卦】(动爻变化后)")
    for idx, line in enumerate(changed_display):
        print(f" 第{6-idx}爻：{line}")

    if moving_line_indices:
        print(f"\n✨ 动爻：第{', '.join(moving_line_indices)}爻")
    else:
        print("\n🔒 静卦（无动爻）")

    print("=" * 50)


if __name__ == "__main__":
    main()
