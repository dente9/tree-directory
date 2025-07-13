import os
import sys
import argparse
import fnmatch
from collections import defaultdict
from colorama import init, Fore, Style

# 初始化 colorama
init()

# ==============================================================================
# 优先级 2: 特殊处理规则
# 仅当项目未被 --include 匹配时，此规则生效。
# 格式: (模式, 可见性, 强制摘要)
SPECIAL_HANDLING_RULES = [
    # (文件夹名字, 可见?, 摘要?)
    ('data', True, True),
    ('dataset', True, True),
    ('log', True, True),
    ('logs', True, True),
    ('pre-trained', True, True),
    ('output', False, False), # 示例: 强制隐藏 output 目录
]
# ==============================================================================

# 优先级 3: 内置的默认忽略规则
BUILTIN_IGNORE_PATTERNS = [
    '**/__pycache__',
    '*.py[cod]', '*.pyd', '*.pyo', '*.pyc',
    '.git',
    '.vscode',
    'node_modules',
    '.venv',
]

def load_gitignore_rules(directory):
    """加载并解析 .gitignore 文件，返回规则列表。"""
    gitignore_path = os.path.join(directory, '.gitignore')
    if not os.path.isfile(gitignore_path):
        return []
    rules = []
    try:
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            for line in f:
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith('#'):
                    if stripped_line.endswith('/'):
                        stripped_line = stripped_line[:-1]
                    rules.append(stripped_line)
    except Exception as e:
        print(f"{Fore.YELLOW}Warning: Could not read .gitignore: {e}{Style.RESET_ALL}")
    return rules

def is_in_ignore_list(item, path, combined_ignore_list):
    """检查一个项目是否在合并的忽略列表中 (优先级 3)。"""
    full_path = os.path.join(path, item)
    for pattern in combined_ignore_list:
        if fnmatch.fnmatch(item, pattern) or fnmatch.fnmatch(full_path, pattern):
            return True
    return False

def tree(directory, max_depth, show_all, include_patterns, combined_ignore_list, force_summary=False, current_depth=0):
    try:
        raw_items = os.listdir(directory)
    except PermissionError:
        indent = '  ' * current_depth
        print(f"{indent}{Fore.RED}Permission denied: {os.path.basename(directory)}{Style.RESET_ALL}")
        return
    except FileNotFoundError:
        indent = '  ' * current_depth
        print(f"{indent}{Fore.RED}Not found: {os.path.basename(directory)}{Style.RESET_ALL}")
        return

    folders = []
    file_types = defaultdict(lambda: [0, []])

    for item in raw_items:
        # --- 按新优先级顺序决定项目的最终状态 ---
        final_visible = None
        final_summary = False

        # 优先级 1: --include 参数
        is_included_by_cli = False
        for pattern in include_patterns:
            if fnmatch.fnmatch(item, pattern) or fnmatch.fnmatch(os.path.join(directory, item), pattern):
                is_included_by_cli = True
                break

        if is_included_by_cli:
            final_visible = True
            final_summary = True

        # 优先级 2: 特殊处理规则 (仅当未被 --include 处理时)
        if final_visible is None:
            for rule_pattern, rule_visible, rule_summary in SPECIAL_HANDLING_RULES:
                if fnmatch.fnmatch(item, rule_pattern):
                    final_visible = rule_visible
                    final_summary = rule_summary
                    break

        # 优先级 3: 忽略列表 (仅当未被更高优先级规则处理时)
        if final_visible is None:
            if is_in_ignore_list(item, directory, combined_ignore_list):
                final_visible = False
            else:
                final_visible = True # 默认可见

        # --- 根据最终状态处理项目 ---
        if not final_visible:
            continue

        full_path = os.path.join(directory, item)
        if os.path.isdir(full_path):
            folders.append({'name': item, 'force_summary': final_summary})
        else:
            _, ext = os.path.splitext(item)
            ext = ext.lower() or ".<no ext>"
            counter_data = file_types[ext]
            counter_data[0] += 1

            # 文件显示是否摘要，只取决于上层传递下来的状态
            is_summary_branch = force_summary
            effective_show_all = show_all and not is_summary_branch
            if effective_show_all or counter_data[0] <= 2:
                counter_data[1].append(item)

    folders.sort(key=lambda x: x['name'])

    indent = '  ' * current_depth
    if current_depth == 0:
        print(f"{Fore.BLUE}{Style.BRIGHT}{os.path.abspath(directory)}{Style.RESET_ALL}/")
    else:
        print(f"{indent}{Fore.BLUE}{Style.BRIGHT}{os.path.basename(directory)}{Style.RESET_ALL}/")

    is_summary_branch_for_files = force_summary
    effective_show_all_for_files = show_all and not is_summary_branch_for_files

    if file_types:
        for ext in sorted(file_types.keys()):
            count, samples = file_types[ext]
            for f in samples:
                print(f"{indent}  {Fore.GREEN}{f}{Style.RESET_ALL}")
            if not effective_show_all_for_files and count > 2:
                print(f"{indent}  {Fore.YELLOW}... ({count-2} more {ext} files){Style.RESET_ALL}")

    if current_depth < max_depth - 1:
        for folder_info in folders:
            folder_path = os.path.join(directory, folder_info['name'])
            # 向下传递摘要状态
            new_force_summary = force_summary or folder_info['force_summary']
            tree(folder_path, max_depth, show_all, include_patterns, combined_ignore_list, new_force_summary, current_depth + 1)

def main():
    parser = argparse.ArgumentParser(
        description='彩色目录树生成器。\n规则优先级: --include > 特殊规则 > .gitignore > 内置规则。',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('path', nargs='?', default=os.getcwd(), help='指定路径，默认当前目录')
    parser.add_argument('-l', '--level', type=int, default=5, help='显示的层级数目，默认是5')
    parser.add_argument('-a', '--all', action='store_true', help='显示所有文件（可被摘要规则覆盖）')
    parser.add_argument(
        '-i', '--include',
        action='append',
        dest='include_patterns',
        default=[],
        help='最高优先级：强制包含某个模式并启用摘要输出。\n可多次使用 (e.g., -i data -i *.log)。'
    )

    args = parser.parse_args()

    if args.level < 1:
        print(f"{Fore.RED}错误：层级数必须大于等于1{Style.RESET_ALL}")
        sys.exit(1)

    target_path = os.path.abspath(args.path)
    gitignore_rules = load_gitignore_rules(target_path)
    combined_ignore_list = BUILTIN_IGNORE_PATTERNS + gitignore_rules

    try:
        tree(target_path, args.level, args.all, args.include_patterns, combined_ignore_list)
    except Exception as e:
        print(f"{Fore.RED}错误: {e}{Style.RESET_ALL}")

if __name__ == '__main__':
    main()