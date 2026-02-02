#!/usr/bin/env python3
"""
大文件扫描器 - 扫描指定目录，找出大文件
"""
import os
import json
from pathlib import Path
from datetime import datetime


def find_large_files(directory, min_size_mb=10, max_results=100):
    """
    扫描目录，找出大于指定大小的文件

    Args:
        directory: 要扫描的目录
        min_size_mb: 最小文件大小（MB）
        max_results: 最大返回结果数

    Returns:
        文件列表，按大小排序
    """
    directory = Path(directory)

    if not directory.exists():
        print(f"❌ 目录不存在: {directory}")
        return []

    print(f"🔍 扫描目录: {directory}")
    print(f"   最小大小: {min_size_mb} MB")
    print(f"   最大结果: {max_results}")
    print()

    large_files = []
    min_size_bytes = min_size_mb * 1024 * 1024

    # 排除的目录
    exclude_dirs = {
        '.git',
        '__pycache__',
        'node_modules',
        '.venv',
        'venv',
        'env',
        '.cache',
        'Cache',
        'Trash',
        '.Trash'
    }

    # 排除的文件类型（可扩展）
    exclude_extensions = {
        '.pyc',
        '.pyo',
        '.pyd',
    }

    print("扫描中... (按 Ctrl+C 停止)")
    print()

    count = 0
    for root, dirs, files in os.walk(directory):
        # 移除排除的目录
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            file_path = Path(root) / file

            try:
                size = file_path.stat().st_size

                # 检查文件大小
                if size >= min_size_bytes:
                    # 检查文件扩展名
                    if file_path.suffix not in exclude_extensions:
                        count += 1
                        large_files.append({
                            'path': str(file_path),
                            'name': file,
                            'size_mb': size / (1024 * 1024),
                            'size_bytes': size,
                            'extension': file_path.suffix,
                            'parent': str(file_path.parent)
                        })

                        # 限制结果数量
                        if len(large_files) >= max_results:
                            print(f"⚠️  已达到最大结果数: {max_results}")
                            break

            except (OSError, PermissionError) as e:
                # 跳过无权限的文件
                continue

    # 按大小降序排序
    large_files.sort(key=lambda x: x['size_bytes'], reverse=True)

    return large_files


def print_large_files(files, show_count=20):
    """
    打印大文件列表

    Args:
        files: 文件列表
        show_count: 显示的文件数量
    """
    if not files:
        print("❌ 没有找到大文件")
        return

    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║                      大文件列表                                  ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()

    # 显示前 N 个文件
    display_files = files[:show_count]

    total_size = sum(f['size_bytes'] for f in files)

    print(f"📊 找到 {len(files)} 个大文件，显示前 {len(display_files)} 个")
    print(f"   总大小: {total_size / (1024*1024*1024):.2f} GB")
    print()

    for i, file in enumerate(display_files, 1):
        size_icon = "🔴" if file['size_mb'] > 1000 else \
                    "🟠" if file['size_mb'] > 100 else "🟡"

        print(f"{i:2d}. {size_icon} {file['size_mb']:8.2f} MB  {file['name']}")

        # 显示相对路径
        home = Path.home()
        try:
            relative = Path(file['path']).relative_to(home)
            print(f"       📁 {relative}")
        except ValueError:
            # 不在 home 目录下
            print(f"       📁 {file['path'][:60]}{'...' if len(file['path']) > 60 else ''}")

        print()

    if len(files) > show_count:
        print(f"... 还有 {len(files) - show_count} 个文件")
        print()


def export_to_json(files, output_path):
    """
    导出结果到 JSON 文件

    Args:
        files: 文件列表
        output_path: 输出文件路径
    """
    with open(output_path, 'w') as f:
        json.dump(files, f, indent=2, ensure_ascii=False)

    print(f"✅ 结果已导出到: {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="大文件扫描器")
    parser.add_argument('directory', nargs='?', default='~',
                       help='要扫描的目录（默认: ~）')
    parser.add_argument('--min-size', type=float, default=10,
                       help='最小文件大小（MB），默认: 10')
    parser.add_argument('--max-results', type=int, default=100,
                       help='最大结果数，默认: 100')
    parser.add_argument('--show', type=int, default=20,
                       help='显示的文件数量，默认: 20')
    parser.add_argument('--export', help='导出结果到 JSON 文件')

    args = parser.parse_args()

    # 展开 ~
    directory = Path(args.directory).expanduser()

    # 扫描
    files = find_large_files(
        directory,
        min_size_mb=args.min_size,
        max_results=args.max_results
    )

    # 显示结果
    print_large_files(files, show_count=args.show)

    # 导出（如果需要）
    if args.export:
        export_path = Path(args.export).expanduser()
        export_to_json(files, export_path)


if __name__ == "__main__":
    main()
