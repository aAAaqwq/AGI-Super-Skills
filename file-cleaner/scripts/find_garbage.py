#!/usr/bin/env python3
"""
垃圾文件扫描器 - 扫描并识别垃圾文件（临时文件、缓存等）
"""
import os
import json
from pathlib import Path
from datetime import datetime


# 垃圾文件模式
GARBAGE_PATTERNS = {
    # 临时文件
    'temp_files': {
        'extensions': ['.tmp', '.temp', '.bak', '.swp', '.DS_Store'],
        'patterns': ['*.tmp', '*.temp', '*.bak'],
        'description': '临时文件',
        'safe_to_delete': True
    },

    # 缓存文件
    'cache_files': {
        'extensions': ['.cache'],
        'patterns': ['__pycache__', '*.pyc', '.pytest_cache'],
        'directories': ['__pycache__', '.cache', 'Cache', 'node_modules/.cache'],
        'description': '缓存文件',
        'safe_to_delete': True
    },

    # 日志文件
    'log_files': {
        'extensions': ['.log'],
        'patterns': ['*.log'],
        'description': '日志文件',
        'safe_to_delete': False  # 日志可能需要用于调试
    },

    # 备份文件
    'backup_files': {
        'extensions': ['.backup', '.old'],
        'patterns': ['*.backup', '*.old'],
        'description': '备份文件',
        'safe_to_delete': True
    },

    # 构建产物
    'build_artifacts': {
        'directories': ['dist', 'build', '.next', 'out', 'target'],
        'description': '构建产物',
        'safe_to_delete': True
    },

    # 编辑器临时文件
    'editor_temp': {
        'extensions': ['.swo', '.swn', '.un~'],
        'patterns': ['.git/*.rej', '*.orig'],
        'description': '编辑器临时文件',
        'safe_to_delete': True
    },

    # 下载临时文件
    'download_temp': {
        'extensions': ['.crdownload', '.part', '.download'],
        'description': '下载临时文件',
        'safe_to_delete': True
    }
}

# 排除的目录（重要系统目录）
EXCLUDE_DIRS = {
    '/proc',
    '/sys',
    '/dev',
    '/run',
    '/tmp',
    '/var/tmp',
    '/usr',
    '/bin',
    '/sbin',
    '/lib',
    '.git',
    '.svn',
    '.hg',
}


def scan_for_garbage(directory, categories=None):
    """
    扫描目录，找出垃圾文件

    Args:
        directory: 要扫描的目录
        categories: 要扫描的垃圾类型（None = 全部）

    Returns:
        垃圾文件列表，按类别分类
    """
    directory = Path(directory).expanduser()

    if not directory.exists():
        print(f"❌ 目录不存在: {directory}")
        return {}

    print(f"🔍 扫描目录: {directory}")
    print()

    # 确定要扫描的类别
    if categories is None:
        categories = list(GARBAGE_PATTERNS.keys())
    else:
        categories = [c for c in categories if c in GARBAGE_PATTERNS]

    # 结果
    garbage_files = {category: [] for category in categories}

    # 总统计
    total_files = 0
    total_size = 0

    for root, dirs, files in os.walk(directory):
        # 移除排除的目录
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for file in files:
            file_path = Path(root) / file

            try:
                # 获取文件信息
                stat = file_path.stat()
                size = stat.st_size
                extension = file_path.suffix.lower()
                filename = file_path.name.lower()
                parent_dir = file_path.parent.name

                # 检查每个类别
                for category in categories:
                    pattern_info = GARBAGE_PATTERNS[category]

                    # 检查扩展名
                    if 'extensions' in pattern_info:
                        if extension in pattern_info['extensions']:
                            garbage_files[category].append({
                                'path': str(file_path),
                                'name': file,
                                'size_mb': size / (1024 * 1024),
                                'size_bytes': size,
                                'extension': extension,
                                'category': category,
                                'description': pattern_info['description'],
                                'safe_to_delete': pattern_info['safe_to_delete'],
                                'parent': str(file_path.parent)
                            })
                            total_files += 1
                            total_size += size
                            break

                    # 检查目录名
                    elif 'directories' in pattern_info:
                        if parent_dir in pattern_info['directories']:
                            # 整个目录都算作垃圾
                            garbage_files[category].append({
                                'path': str(file_path),
                                'name': file,
                                'size_mb': size / (1024 * 1024),
                                'size_bytes': size,
                                'extension': extension,
                                'category': category,
                                'description': pattern_info['description'],
                                'safe_to_delete': pattern_info['safe_to_delete'],
                                'parent': str(file_path.parent),
                                'is_directory': parent_dir
                            })
                            total_files += 1
                            total_size += size
                            break

                    # 检查文件名模式
                    elif 'patterns' in pattern_info:
                        for pattern in pattern_info['patterns']:
                            # 简单的通配符匹配
                            if pattern.startswith('*.'):
                                pattern_ext = pattern[1:]
                                if extension == pattern_ext:
                                    garbage_files[category].append({
                                        'path': str(file_path),
                                        'name': file,
                                        'size_mb': size / (1024 * 1024),
                                        'size_bytes': size,
                                        'extension': extension,
                                        'category': category,
                                        'description': pattern_info['description'],
                                        'safe_to_delete': pattern_info['safe_to_delete'],
                                        'parent': str(file_path.parent)
                                    })
                                    total_files += 1
                                    total_size += size
                                    break

            except (OSError, PermissionError) as e:
                # 跳过无权限的文件
                continue

    # 按类别汇总
    for category in categories:
        files = garbage_files[category]
        category_size = sum(f['size_bytes'] for f in files)
        garbage_files[category] = {
            'files': files,
            'count': len(files),
            'total_size_mb': category_size / (1024 * 1024),
            'description': GARBAGE_PATTERNS[category]['description'],
            'safe_to_delete': GARBAGE_PATTERNS[category]['safe_to_delete']
        }

    # 总计
    garbage_files['summary'] = {
        'total_files': total_files,
        'total_size_mb': total_size / (1024 * 1024),
        'categories_scanned': len(categories)
    }

    return garbage_files


def print_garbage_results(results, show_details=10):
    """
    打印垃圾文件扫描结果

    Args:
        results: 扫描结果
        show_details: 每个类别显示的详细数量
    """
    if not results:
        print("❌ 没有扫描到垃圾文件")
        return

    summary = results.get('summary', {})

    print("╔═════════════════════════════════════════════════════════════════╗")
    print("║                       垃圾文件扫描结果                             ║")
    print("╚═════════════════════════════════════════════════════════════════╝")
    print()

    # 摘要
    print("📊 扫描摘要")
    print()
    print(f"   扫描类别: {summary.get('categories_scanned', 0)}")
    print(f"   垃圾文件: {summary.get('total_files', 0)} 个")
    print(f"   总大小: {summary.get('total_size_mb', 0):.2f} MB")
    print()

    # 按类别显示
    categories = [c for c in results.keys() if c != 'summary']

    if not categories:
        print("✅ 没有发现垃圾文件！")
        return

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    total_safe = 0
    total_unsafe = 0

    for category in categories:
        if category == 'summary':
            continue

        data = results[category]
        files = data.get('files', [])
        count = data.get('count', 0)
        size_mb = data.get('total_size_mb', 0)
        description = data.get('description', '')
        safe_to_delete = data.get('safe_to_delete', False)

        if count == 0:
            continue

        # 状态图标
        if safe_to_delete:
            status_icon = "🟢"
            status_text = "安全删除"
            total_safe += count
        else:
            status_icon = "🟡"
            status_text = "需确认"
            total_unsafe += count

        print(f"{status_icon} {description} ({count} 个, {size_mb:.2f} MB)")
        print(f"   状态: {status_text}")

        # 显示前几个文件
        for i, file in enumerate(files[:show_details], 1):
            relative = Path(file['path'])
            try:
                home = Path.home()
                relative = relative.relative_to(home)
                display_path = f"~/{relative}"
            except ValueError:
                display_path = file['path'][:60]

            print(f"   {i}. {file['name'][:50]}")
            print(f"      📁 {display_path}")

        if count > show_details:
            print(f"   ... 还有 {count - show_details} 个文件")

        print()

    # 安全提示
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print(f"🟢 可安全删除: {total_safe} 个文件")
    print(f"🟡 需要确认: {total_unsafe} 个文件（日志、备份等）")
    print()
    print("💡 提示:")
    print("  • 查看文件内容再删除，确认没有重要数据")
    print("  • 日志文件可以先归档，一段时间后再删除")
    print("  • 缓存文件可以安全删除，会自动重建")


def generate_cleanup_script(results, output_path):
    """
    生成清理脚本

    Args:
        results: 扫描结果
        output_path: 输出脚本路径
    """
    with open(output_path, 'w') as f:
        f.write("#!/bin/bash\n")
        f.write(f"# 自动生成的垃圾文件清理脚本\n")
        f.write(f"# 生成时间: {datetime.now().isoformat()}\n")
        f.write(f"# ⚠️  使用前请仔细检查！\n\n")

        f.write("echo \"🗑️  垃圾文件清理脚本\"\n")
        f.write("echo \"=\"\n\n")

        # 只包含安全删除的文件
        for category in results.keys():
            if category == 'summary':
                continue

            data = results[category]
            if not data.get('safe_to_delete', False):
                f.write(f"# ⚠️  跳过 {data.get('description')} (需要手动确认)\n\n")
                continue

            files = data.get('files', [])
            for file in files:
                f.write(f"rm -f \"{file['path']}\"\n")

        f.write("\necho \"✅ 清理完成\"\n")
        f.write("echo \"⚠️  请确认没有误删！\"\n")

    print(f"✅ 清理脚本已生成: {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="垃圾文件扫描器")
    parser.add_argument('directory', nargs='?', default='~',
                       help='要扫描的目录（默认: ~）')
    parser.add_argument('--categories', nargs='+',
                       choices=list(GARBAGE_PATTERNS.keys()),
                       help='要扫描的垃圾类型（默认: 全部）')
    parser.add_argument('--show', type=int, default=10,
                       help='每个类别显示的文件数量（默认: 10）')
    parser.add_argument('--export', help='导出结果到 JSON 文件')
    parser.add_argument('--script', help='生成清理脚本路径')

    args = parser.parse_args()

    # 展开路径
    directory = Path(args.directory).expanduser()

    # 扫描
    results = scan_for_garbage(
        directory,
        categories=args.categories
    )

    # 显示结果
    print_garbage_results(results, show_details=args.show)

    # 导出结果
    if args.export:
        export_path = Path(args.export).expanduser()
        with open(export_path, 'w') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"✅ 结果已导出到: {export_path}")

    # 生成清理脚本
    if args.script:
        script_path = Path(args.script).expanduser()
        generate_cleanup_script(results, script_path)


if __name__ == "__main__":
    main()
