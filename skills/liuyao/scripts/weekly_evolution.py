#!/usr/bin/env python3
"""
六爻技能每周进化脚本

核心理念："解一卦就是传一道，说一言就是传一智"

每周手动检查和更新技能（需用户主动运行，非定时任务），确保：
1. 解卦风格遵循贫道人设
2. 文化传承到位
3. 案例库丰富
4. 内容质量提升
"""

import os
import json
from datetime import datetime
from pathlib import Path

# 使用脚本所在目录作为工作区（相对路径，避免硬编码）
SCRIPT_DIR = Path(__file__).parent.resolve()
WORKSPACE = SCRIPT_DIR.parent  # skill root: liuyao/
LOG_FILE = WORKSPACE / "logs" / "evolution_log.md"
SKILL_FILE = WORKSPACE / "SKILL.md"
CASES_FILE = WORKSPACE / "references" / "cases.md"

def log(message):
    """记录进化日志"""
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{message}\n")

def check_skill_quality():
    """检查技能质量"""
    if not SKILL_FILE.exists():
        return {"status": "error", "message": "SKILL.md不存在"}

    with open(SKILL_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # 检查关键元素
    checks = {
        "has_persona": "## 📜 贫道人设" in content,
        "has_core_slogan": "解一卦就是传一道" in content,
        "has_style_guide": "## 🎭 解卦输出风格" in content,
        "has_confucian": "孔子" in content or "论语" in content,
        "has_taoist": "老子" in content or "道德经" in content,
        "has_sunzi": "孙子" in content or "孙子兵法" in content,
        "uses_pindao": "贫道" in content,
        "uses_jushi": "居士" in content,
    }

    passed = sum(checks.values())
    total = len(checks)

    return {
        "status": "ok" if passed == total else "needs_improvement",
        "passed": passed,
        "total": total,
        "checks": checks
    }

def check_cases():
    """检查案例库"""
    if not CASES_FILE.exists():
        return {"status": "error", "message": "案例库不存在"}

    with open(CASES_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # 计算案例数量
    case_count = content.count("### 案例")

    # 检查是否有贫道风格的引用
    has_cultural_refs = any(keyword in content for keyword in [
        "孔子曰", "老子曰", "《易经》", "《论语》", "《道德经》"
    ])

    return {
        "case_count": case_count,
        "has_cultural_refs": has_cultural_refs,
        "status": "ok"
    }

def check_references():
    """检查参考资料"""
    ref_dir = WORKSPACE / "references"
    if not ref_dir.exists():
        return {"status": "error", "message": "references目录不存在"}

    files = list(ref_dir.glob("*.md"))
    total_lines = 0

    for f in files:
        with open(f, "r", encoding="utf-8") as file:
            total_lines += len(file.readlines())

    return {
        "files": len(files),
        "total_lines": total_lines,
        "status": "ok"
    }

def generate_suggestions(quality, cases, refs):
    """基于检查结果生成建议"""
    suggestions = []

    # 质量检查建议
    if quality["status"] != "ok":
        failed = [k for k, v in quality["checks"].items() if not v]
        suggestions.append(f"📝 质量改进：需要在SKILL.md中加强 {', '.join(failed)}")

    # 案例建议
    if cases["case_count"] < 15:
        suggestions.append("📚 建议增加案例库，当前案例不足15个")

    if not cases["has_cultural_refs"]:
        suggestions.append("📖 建议在案例中添加文化引用（孔子、老子等）")

    # 参考资料建议
    if refs["total_lines"] < 3000:
        suggestions.append("📈 建议扩充参考资料库，当前内容较少")

    # 固定建议
    suggestions.append("🎯 下周重点：优化解卦话术，增加文化内涵")
    suggestions.append("💡 可考虑：添加《易传》十翼内容、梅花易数基础")

    return suggestions

def main():
    print("🔮 六爻技能每周进化检查")
    print("=" * 40)
    print(f"核心理念：解一卦就是传一道，说一言就是传一智")
    print()

    # 执行各项检查
    print("📊 正在检查技能质量...")
    quality = check_skill_quality()
    print(f"   质量检查：{quality['passed']}/{quality['total']} 项通过")

    print("📚 正在检查案例库...")
    cases = check_cases()
    print(f"   案例数量：{cases['case_count']} 个")
    print(f"   文化引用：{'✅ 有' if cases['has_cultural_refs'] else '❌ 需添加'}")

    print("📖 正在检查参考资料...")
    refs = check_references()
    print(f"   参考文件：{refs['files']} 个，约 {refs['total_lines']} 行")

    # 生成建议
    print()
    suggestions = generate_suggestions(quality, cases, refs)

    print("💡 进化建议：")
    for s in suggestions:
        print(f"   {s}")

    # 记录日志
    log(f"""### 本周检查结果

**技能质量**：{quality['passed']}/{quality['total']} 项通过
- 通过项：{', '.join([k for k, v in quality['checks'].items() if v])}
- 待改进：{', '.join([k for k, v in quality['checks'].items() if not v]) if any(quality['checks'].values()) else '无'}

**案例库**：{cases['case_count']} 个案例
**参考资料**：{refs['files']} 个文件，约 {refs['total_lines']} 行

### 建议
""")
    for s in suggestions:
        log(f"- {s}")

    print()
    print("✅ 每周检查完成！")
    print("如需手动触发进化，请说 '六爻技能进化'")

if __name__ == "__main__":
    main()