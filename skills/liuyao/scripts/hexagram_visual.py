#!/usr/bin/env python3
"""
六爻卦象生成器
根据6次掷硬币结果生成卦象
"""

import sys

# 八卦符号（Unicode）
BAGUA_SYMBOLS = {
    "☰": "乾", "☱": "兑", "☲": "离", "☳": "震",
    "☴": "巽", "☵": "坎", "☶": "艮", "☷": "坤"
}

# 爻转八卦映射
YAO_TO_GUA = {
    "111": "☰",  # 三连，乾
    "110": "☱",  # 上缺，兑
    "101": "☲",  # 中虚，离
    "100": "☳",  # 仰盂，震
    "011": "☴",  # 下断，巽
    "010": "☵",  # 中满，坎
    "001": "☶",  # 覆碗，艮
    "000": "☷",  # 六断，坤
}

# 变爻规则
CHANGE_MAP = {
    "111": "000",  # 老阳变阴
    "000": "111",  # 老阴变阳
    "110": "110",  # 少阳不变
    "101": "101",  # 少阳不变
    "011": "011",  # 少阳不变
    "010": "010",  # 少阴不变
    "001": "001",  # 少阴不变
}

def coins_to_binary(result: str) -> str:
    """将掷硬币结果转换为二进制"""
    # 正=1，反=0
    mapping = {
        "正正正": "111",  # 老阳O
        "反反反": "000",  # 老阴X
        "正正反": "110",  # 少阳—
        "正反正": "110",  # 少阳—
        "反正正": "110",  # 少阳—
        "正反反": "010",  # 少阴--
        "反正反": "010",  # 少阴--
        "反反正": "010",  # 少阴--
    }
    return mapping.get(result, "???")


def generate_hexagram(yao_list: list) -> dict:
    """生成卦象"""
    yao_binary = yao_list[::-1]  # 反转，从初爻开始
    
    # 上下卦
    gua_lower = yao_binary[0] + yao_binary[1] + yao_binary[2]
    gua_upper = yao_binary[3] + yao_binary[4] + yao_binary[5]
    
    lower_gua = YAO_TO_GUA.get(gua_lower, "?")
    upper_gua = YAO_TO_GUA.get(gua_upper, "?")
    
    # 变卦
    changed_lower = CHANGE_MAP.get(gua_lower, gua_lower)
    changed_upper = CHANGE_MAP.get(gua_upper, gua_upper)
    changed_lower_gua = YAO_TO_GUA.get(changed_lower, "?")
    changed_upper_gua = YAO_TO_GUA.get(changed_upper, "?")
    
    # 动爻
    dongyao = []
    if gua_lower != changed_lower:
        dongyao.append("初爻")
    if gua_upper != changed_upper:
        dongyao.append("上爻")
    
    return {
        "lower": lower_gua,
        "upper": upper_gua,
        "lower_name": BAGUA_SYMBOLS.get(lower_gua, "?"),
        "upper_name": BAGUA_SYMBOLS.get(upper_gua, "?"),
        "main_gua": f"{BAGUA_SYMBOLS.get(lower_gua, '')}{BAGUA_SYMBOLS.get(upper_gua, '')}",
        "changed_lower": changed_lower_gua,
        "changed_upper": changed_upper_gua,
        "changed_gua": f"{BAGUA_SYMBOLS.get(changed_lower_gua, '')}{BAGUA_SYMBOLS.get(changed_upper_gua, '')}",
        "dongyao": dongyao,
    }


def print_hexagram(yao_list: list, results: list = None):
    """打印卦象"""
    if results is None:
        results = yao_list
    
    print("\n" + "═" * 40)
    print("       六 爻 卦 象")
    print("═" * 40)
    
    # 从上爻往下打印
    for i in range(5, -1, -1):
        yao = yao_list[i]
        pos_names = ["上爻", "五爻", "四爻", "三爻", "二爻", "初爻"]
        pos = pos_names[i]
        
        # 阳爻/阴爻
        if yao in ["111", "110", "101", "011"]:
            line = "━━━"
            mark = "  ○" if yao == "111" else ""
        else:
            line = "━ ━"
            mark = "  ×" if yao == "000" else ""
        
        # 结果描述
        res = results[i] if i < len(results) else ""
        
        print(f"│  {pos}  {line}{mark:5}  │  {res}")
        print("─" * 40)
    
    # 生成卦象信息
    gua_info = generate_hexagram(yao_list)
    
    print(f"│ 主卦：{gua_info['lower_name']}{gua_info['upper_name']}  {gua_info['lower']}{gua_info['upper']}        │")
    if gua_info['dongyao']:
        print(f"│ 动爻：{','.join(gua_info['dongyao'])}               │")
        print(f"│ 变卦：{BAGUA_SYMBOLS.get(gua_info['changed_lower'], '?')}{BAGUA_SYMBOLS.get(gua_info['changed_upper'], '?')}  {gua_info['changed_lower']}{gua_info['changed_upper']}        │")
    print("═" * 40)
    
    return gua_info


def main():
    print("六爻卦象生成器")
    print("请输入6次掷硬币结果（正=正面，反=背面）")
    print("═" * 40)
    
    results = []
    for i in range(6):
        pos_names = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"]
        print(f"\n第{i+1}次（{pos_names[i]}）：")
        while True:
            user_input = input("输入（如：正正反）：").strip()
            if user_input in ["正正正", "反反反", "正正反", "正反正", "反正正", "正反反", "反正反", "反反正"]:
                results.append(user_input)
                break
            print("输入错误！请输入：正正正、正正反、正反正、反正正、正反反、反正反、反反正")
    
    # 生成并打印卦象
    yao_list = [coins_to_binary(r) for r in results]
    gua_info = print_hexagram(yao_list, results)
    
    print(f"\n📋 卦象总结：")
    print(f"   主卦：{gua_info['main_gua']} ({gua_info['lower']}{gua_info['upper']})")
    if gua_info['dongyao']:
        print(f"   动爻：{','.join(gua_info['dongyao'])}")
        print(f"   变卦：{gua_info['changed_gua']} ({gua_info['changed_lower']}{gua_info['changed_upper']})")
    print()


if __name__ == "__main__":
    main()
