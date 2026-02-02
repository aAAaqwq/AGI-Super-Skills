#!/usr/bin/env python3
"""
交互式文件清理工具
"""
import json
import shutil
from pathlib import Path
from datetime import datetime


def load_scan_results(json_path):
    """
    加载扫描结果

    Args:
        json_path: JSON 文件路径

    Returns:
        扫描结果字典
    """
    json_path = Path(json_path).expanduser()

    if not json_path.exists():
        print(f"❌ 扫描结果文件不存在: {json_path}")
        return None

    with open(json_path, 'r') as f:
        return json.load(f)


def display_selection_menu(results, scan_type='garbage'):
    """
    显示选择菜单

    Args:
        results: 扫描结果
        scan_type: 扫描类型 ('garbage' 或 'large')

    Returns:
        用户选择的文件列表
    """
    if scan_type == 'garbage':
        return display_garbage_menu(results)
    elif scan_type == 'large':
        return display_large_files_menu(results)
    else:
        print(f"❌ 未知的扫描类型: {scan_type}")
        return []


def display_garbage_menu(results):
    """
    显示垃圾文件选择菜单

    Args:
        results: 垃圾文件扫描结果

    Returns:
        用户选择的文件列表
    """
    selected_files = []

    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║                   选择要清理的垃圾文件                        ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()

    # 按类别显示
    categories = [c for c in results.keys() if c != 'summary']

    for category in categories:
        data = results[category]
        files = data.get('files', [])

        if not files:
            continue

        description = data.get('description', '')
        count = data.get('count', 0)
        size_mb = data.get('total_size_mb', 0)
        safe_to_delete = data.get('safe_to_delete', False)

        # 显示类别信息
        status_icon = "🟢" if safe_to_delete else "🟡"
        print(f"{status_icon} {description} ({count} 个文件, {size_mb:.2f} MB)")

        # 询问是否清理该类别
        if safe_to_delete:
            print(f"   [A] 全选    [S] 跳过")
            print(f"   [1-{count}] 选择文件")

            # 简化：全选或跳过
            while True:
                choice = input(f"   清理全部 [A/S]? ").strip().upper()

                if choice == 'A':
                    selected_files.extend(files)
                    print(f"   ✅ 已选择全部 {count} 个文件")
                    break
                elif choice == 'S':
                    print(f"   ⏭️  跳过")
                    break
                else:
                    print("   请输入 A 或 S")
        else:
            print(f"   [S] 跳过 (需要手动确认)")

            while True:
                choice = input(f"   跳过 [S/Y]? ").strip().upper()

                if choice == 'S':
                    print(f"   ⏭️  跳过")
                    break
                elif choice == 'Y':
                    print(f"   ⏭️  跳过")
                    break
                else:
                    print("   请输入 S 或 Y")

        print()

    return selected_files


def display_large_files_menu(results):
    """
    显示大文件选择菜单

    Args:
        results: 大文件扫描结果

    Returns:
        用户选择的文件列表
    """
    selected_files = []

    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║                   选择要清理的大文件                          ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()

    # 显示文件列表
    for i, file in enumerate(results, 1):
        size_icon = "🔴" if file['size_mb'] > 1000 else \
                    "🟠" if file['size_mb'] > 100 else "🟡"

        print(f"{i:2d}. {size_icon} {file['size_mb']:8.2f} MB")
        print(f"       📁 {file['name']}")

        # 显示相对路径
        home = Path.home()
        try:
            relative = Path(file['path']).relative_to(home)
            print(f"       📍 ~/{relative}")
        except ValueError:
            short_path = file['path'][:60]
            print(f"       📍 {short_path}{'...' if len(file['path']) > 60 else ''}")

        print()

    # 选择文件
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print("输入要删除的文件编号（用逗号分隔，或 'all' 删除全部）")
    print("输入 'cancel' 取消")
    print()

    while True:
        choice = input("选择: ").strip()

        if choice.lower() == 'cancel':
            print("❌ 已取消")
            return []
        elif choice.lower() == 'all':
            selected_files = results.copy()
            print(f"✅ 已选择全部 {len(results)} 个文件")
            break
        else:
            # 解析编号
            try:
                indices = [int(x.strip()) - 1 for x in choice.split(',')]

                # 验证索引
                valid_indices = []
                for idx in indices:
                    if 0 <= idx < len(results):
                        valid_indices.append(idx)
                    else:
                        print(f"⚠️  无效的编号: {idx + 1}")

                selected_files = [results[i] for i in valid_indices]
                print(f"✅ 已选择 {len(selected_files)} 个文件")
                break

            except ValueError:
                print("❌ 输入格式错误，请输入编号（如: 1,3,5）")

    return selected_files


def confirm_cleanup(files):
    """
    确认清理操作

    Args:
        files: 要清理的文件列表

    Returns:
        是否确认清理
    """
    if not files:
        print("❌ 没有选择任何文件")
        return False

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print("⚠️  确认清理")
    print()
    print(f"将删除 {len(files)} 个文件")

    total_size = sum(f.get('size_bytes', f.get('size_mb', 0) * 1024 * 1024)
                   for f in files)
    print(f"总大小: {total_size / (1024 * 1024 * 1024):.2f} GB")
    print()

    # 显示前几个文件
    for file in files[:5]:
        print(f"  • {file.get('name', file.get('path', ''))}")

    if len(files) > 5:
        print(f"  ... 和其他 {len(files) - 5} 个文件")

    print()
    print("⚠️  此操作不可撤销！")
    print()

    choice = input("确认删除 [yes/no]? ").strip().lower()

    return choice in ['yes', 'y']


def cleanup_files(files, dry_run=False):
    """
    清理文件

    Args:
        files: 要清理的文件列表
        dry_run: 是否为预演模式（不实际删除）

    Returns:
        成功删除的文件数量
    """
    if not files:
        return 0

    print()
    print("🗑️  开始清理...")
    print()

    if dry_run:
        print("🔍 预演模式（不会实际删除文件）")
        print()

    success_count = 0
    failed_count = 0

    for file in files:
        file_path = file.get('path')
        if not file_path:
            continue

        try:
            if dry_run:
                print(f"  [PRETEND] 删除: {file_path}")
                success_count += 1
            else:
                # 删除文件或目录
                path_obj = Path(file_path)
                if path_obj.is_dir():
                    shutil.rmtree(path_obj)
                else:
                    path_obj.unlink()

                print(f"  ✅ 已删除: {file.get('name', file_path)}")
                success_count += 1

        except Exception as e:
            print(f"  ❌ 删除失败: {file.get('name', file_path)}")
            print(f"      错误: {e}")
            failed_count += 1

    print()
    print(f"📊 清理完成:")
    print(f"   成功: {success_count}")
    print(f"   失败: {failed_count}")

    return success_count


def main():
    import argparse

    parser = argparse.ArgumentParser(description="交互式文件清理工具")
    parser.add_argument('scan_result', help='扫描结果 JSON 文件')
    parser.add_argument('--type', choices=['garbage', 'large'],
                       default='garbage',
                       help='扫描结果类型（默认: garbage）')
    parser.add_argument('--dry-run', action='store_true',
                       help='预演模式，不实际删除文件')

    args = parser.parse_args()

    # 加载扫描结果
    print(f"📂 加载扫描结果: {args.scan_result}")
    print()

    results = load_scan_results(args.scan_result)

    if not results:
        print("❌ 无法加载扫描结果")
        return

    # 显示选择菜单
    selected_files = display_selection_menu(results, scan_type=args.type)

    if not selected_files:
        print("❌ 没有选择任何文件")
        return

    # 确认清理
    if not confirm_cleanup(selected_files):
        print("❌ 已取消清理")
        return

    # 执行清理
    cleanup_files(selected_files, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
