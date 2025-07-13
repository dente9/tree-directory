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
SPECIAL_HANDLING_RULES = [
    ('data', True, True), ('dataset', True, True),
    ('log', True, True), ('logs', True, True),
    ('pre-trained', True, True), ('output', False, False),
]
# ==============================================================================

# 优先级 3: 内置的默认忽略规则
BUILTIN_IGNORE_PATTERNS = [
    '**/__pycache__', '*.py[cod]', '*.pyd', '*.pyo', '*.pyc',
    '.git', '.vscode', 'node_modules', '.venv',
]

def load_gitignore_rules(directory):
    gitignore_path = os.path.join(directory, '.gitignore')
    if not os.path.isfile(gitignore_path): return []
    rules = []
    try:
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            for line in f:
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith('#'):
                    if stripped_line.endswith('/'): stripped_line = stripped_line[:-1]
                    rules.append(stripped_line)
    except Exception as e:
        print(f"{Fore.YELLOW}Warning: Could not read .gitignore: {e}{Style.RESET_ALL}")
    return rules

def is_in_ignore_list(item, path, combined_ignore_list):
    full_path = os.path.join(path, item)
    for pattern in combined_ignore_list:
        if fnmatch.fnmatch(item, pattern) or fnmatch.fnmatch(full_path, pattern):
            return True
    return False

def tree(directory, max_depth, show_all, include_patterns, combined_ignore_list, force_summary=False, current_depth=0):
    try:
        raw_items = os.listdir(directory)
    except PermissionError:
        print(f"{'  ' * current_depth}{Fore.RED}Permission denied: {os.path.basename(directory)}{Style.RESET_ALL}")
        return
    except FileNotFoundError:
        print(f"{'  ' * current_depth}{Fore.RED}Not found: {os.path.basename(directory)}{Style.RESET_ALL}")
        return

    folders, file_types = [], defaultdict(lambda: [0, []])
    visible_item_infos = []

    for item in raw_items:
        final_visible, final_summary = None, False

        if any(fnmatch.fnmatch(item, p) or fnmatch.fnmatch(os.path.join(directory, item), p) for p in include_patterns):
            final_visible, final_summary = True, True

        if final_visible is None:
            for p, v, s in SPECIAL_HANDLING_RULES:
                if fnmatch.fnmatch(item, p): final_visible, final_summary = v, s; break

        if final_visible is None:
            final_visible = not is_in_ignore_list(item, directory, combined_ignore_list)

        if final_visible:
            visible_item_infos.append({'name': item, 'force_summary': final_summary, 'is_dir': os.path.isdir(os.path.join(directory, item))})

    visible_item_infos.sort(key=lambda x: (x['is_dir'], x['name']))

    for info in visible_item_infos:
        if info['is_dir']: folders.append(info)
        else:
            item = info['name']; _, ext = os.path.splitext(item)
            ext = ext.lower() or ".<no ext>"; counter_data = file_types[ext]
            counter_data[0] += 1
            if (show_all and not force_summary) or counter_data[0] <= 2: counter_data[1].append(item)

    indent = '  ' * current_depth
    print(f"{indent}{Fore.BLUE}{Style.BRIGHT}{os.path.basename(directory) if current_depth > 0 else os.path.abspath(directory)}{Style.RESET_ALL}/")

    if file_types:
        for ext in sorted(file_types.keys()):
            count, samples = file_types[ext]
            for f in samples: print(f"{indent}  {Fore.GREEN}{f}{Style.RESET_ALL}")
            if not (show_all and not force_summary) and count > 2:
                print(f"{indent}  {Fore.YELLOW}... ({count-2} more {ext} files){Style.RESET_ALL}")

    if current_depth < max_depth - 1:
        for folder_info in folders:
            tree(os.path.join(directory, folder_info['name']), max_depth, show_all, include_patterns, combined_ignore_list, force_summary or folder_info['force_summary'], current_depth + 1)

def run_log_mode(args, combined_ignore_list):
    """【分析模式】只运行分析和日志输出，不生成树。"""
    target_path = os.path.abspath(args.path)

    try:
        raw_items = os.listdir(target_path)
    except Exception as e:
        print(f"{Fore.RED}错误: 无法读取目录 '{target_path}': {e}{Style.RESET_ALL}")
        return

    analysis_results = []
    for item in raw_items:
        # 按优先级顺序决定项目的最终状态
        result = {'name': item, 'status': '', 'color': '', 'reason': '', 'summary': ''}
        final_visible = None

        if any(fnmatch.fnmatch(item, p) for p in args.include_patterns):
            final_visible, result['summary'] = True, '(摘要)'
            result['status'], result['color'], result['reason'] = '[可见]', Fore.GREEN, '-i 参数'

        if final_visible is None:
            for p, v, s in SPECIAL_HANDLING_RULES:
                if fnmatch.fnmatch(item, p):
                    final_visible, result['summary'] = v, '(摘要)' if s else ''
                    result['reason'] = '特殊规则'
                    if v: result['status'], result['color'] = '[可见]', Fore.GREEN
                    else: result['status'], result['color'] = '[忽略]', Fore.RED
                    break

        if final_visible is None:
            if is_in_ignore_list(item, target_path, combined_ignore_list):
                final_visible = False
                result['status'], result['color'], result['reason'] = '[忽略]', Fore.RED, '.gitignore/内置'
            else:
                final_visible = True
                result['status'], result['color'], result['reason'] = '[可见]', Fore.CYAN, '默认'

        result['is_visible'] = final_visible
        analysis_results.append(result)

    # --- 开始打印报告 ---
    print(f"{Fore.CYAN}--- 分析模式: {target_path} ---{Style.RESET_ALL}")

    # 规则来源摘要
    gitignore_rules_count = len(load_gitignore_rules(target_path))
    print(f"{Fore.YELLOW}[规则来源]{Style.RESET_ALL} .gitignore: {gitignore_rules_count} 条, 内置: {len(BUILTIN_IGNORE_PATTERNS)} 条")

    # 一级条目分析摘要
    visible_count = sum(1 for r in analysis_results if r['is_visible'])
    ignored_items = [r['name'] for r in analysis_results if not r['is_visible']]
    ignored_count = len(ignored_items)
    ignored_names_str = f" ({', '.join(ignored_items)})" if ignored_items else ""
    print(f"{Fore.YELLOW}[一级条目]{Style.RESET_ALL} 总数: {len(raw_items)}, 可见: {visible_count}, 忽略: {ignored_count}{ignored_names_str}")

    print(f"{Fore.CYAN}{'-'*70}{Style.RESET_ALL}")

    # 详细列表
    # 对齐格式: 名称(30), 状态(8), 摘要(8), 原因(15)
    for res in sorted(analysis_results, key=lambda x: (not x['is_visible'], x['name'])):
        name_part = f"{res['color']}{res['name']:<30}{Style.RESET_ALL}"
        status_part = f"{res['color']}{res['status']:<8}{Style.RESET_ALL}"
        summary_part = f"{Fore.YELLOW}{res['summary']:<8}{Style.RESET_ALL}"
        reason_part = f"(来源: {res['reason']})"
        print(f"  {name_part} {status_part} {summary_part} {reason_part}")

def main():
    parser = argparse.ArgumentParser(
        description='彩色目录树生成器。\n规则优先级: --include > 特殊规则 > .gitignore > 内置规则。',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('path', nargs='?', default=os.getcwd(), help='指定路径，默认当前目录')
    parser.add_argument('-l', '--level', type=int, default=5, help='显示的层级数目，默认是5')
    parser.add_argument('-a', '--all', action='store_true', help='显示所有文件（可被摘要规则覆盖）')
    parser.add_argument('-i', '--include', action='append', dest='include_patterns', default=[], help='最高优先级：强制包含某个模式并启用摘要输出。\n可多次使用 (e.g., -i data -i *.log)。')
    parser.add_argument('--log', action='store_true', help='【分析模式】不显示目录树，仅输出规则和顶层目录的分析日志。')

    args = parser.parse_args()

    if args.level < 1:
        print(f"{Fore.RED}错误：层级数必须大于等于1{Style.RESET_ALL}")
        sys.exit(1)

    target_path = os.path.abspath(args.path)
    combined_ignore_list = BUILTIN_IGNORE_PATTERNS + load_gitignore_rules(target_path)

    if args.log:
        run_log_mode(args, combined_ignore_list)
    else:
        try:
            tree(target_path, args.level, args.all, args.include_patterns, combined_ignore_list)
        except Exception as e:
            print(f"{Fore.RED}错误: {e}{Style.RESET_ALL}")

if __name__ == '__main__':
    main()