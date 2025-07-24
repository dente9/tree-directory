import os
import sys
import argparse
import fnmatch
from collections import defaultdict
from colorama import init, Fore, Style

# 初始化 colorama, autoreset=True 确保每个print后的颜色被重置
init(autoreset=True)

# ==============================================================================
# 优先级 2: 特殊处理规则 (支持 fnmatch 通配符)
# 格式: (模式, 是否可见, 是否强制摘要)
# ==============================================================================
SPECIAL_HANDLING_RULES = [
    ('data*', True, True),       # 匹配 data, dataset, data_v2 等
    ('log*', True, True),        # 匹配 log, logs 等
    ('pre-trained', True, True), # 保持精确匹配或按需改为 'pre-trained*'
    ('output*', False, False),   # 匹配 output, output_images 等并忽略它们
]

# ==============================================================================
# 优先级 3: 内置的默认忽略规则 (精简优化版)
# ==============================================================================
BUILTIN_IGNORE_PATTERNS = [
    '**/.*',                # 匹配所有深度的点文件/目录 (覆盖 .git, .vscode, .venv)
    '**/__pycache__',
    '**/node_modules',      # 确保匹配任何深度的 node_modules
    '*.py[cod]', '*.pyd', '*.pyo', '*.pyc',
    'test*',                # 保留，因为用户可能想忽略非点开头的测试目录
]

def load_gitignore_rules(directory):
    """从 .gitignore 文件加载忽略规则。"""
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
        print(f"{Fore.YELLOW}Warning: Could not read .gitignore: {e}")
    return rules

def get_item_final_state(item, path, include_patterns, combined_ignore_list):
    """
    按优先级决定单个项目的最终状态 (是否可见, 是否强制摘要)。
    优先级: include > special > ignore > default
    返回: (isVisible, forceSummary)
    """
    full_path = os.path.join(path, item).replace('\\', '/')

    for p in include_patterns:
        if fnmatch.fnmatch(item, p) or fnmatch.fnmatch(full_path, p):
            return True, True

    for p, v, s in SPECIAL_HANDLING_RULES:
        if fnmatch.fnmatch(item, p):
            return v, s

    for pattern in combined_ignore_list:
        if fnmatch.fnmatch(item, pattern) or fnmatch.fnmatch(full_path, pattern):
            return False, False

    return True, False

def tree(directory, max_depth, show_all, include_patterns, combined_ignore_list, max_count, force_summary=False, current_depth=0):
    """递归地生成并打印目录树。"""
    try:
        raw_items = os.listdir(directory)
    except PermissionError:
        print(f"{'  ' * current_depth}{Fore.RED}Permission denied: {os.path.basename(directory)}")
        return
    except FileNotFoundError:
        print(f"{'  ' * current_depth}{Fore.RED}Not found: {os.path.basename(directory)}")
        return

    folders, file_types = [], defaultdict(lambda: {'count': 0, 'samples': []})
    saturated_exts = set()

    visible_items = []
    for item in raw_items:
        isVisible, item_force_summary = get_item_final_state(item, directory, include_patterns, combined_ignore_list)
        if isVisible:
            visible_items.append({
                'name': item,
                'force_summary': item_force_summary,
                'is_dir': os.path.isdir(os.path.join(directory, item))
            })

    visible_items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))

    # 处理文件，应用摘要逻辑 (最终优雅版)
    for info in visible_items:
        if info['is_dir']:
            folders.append(info)
        else:
            item_name = info['name']
            _, ext = os.path.splitext(item_name)
            ext = ext.lower() or ".<no ext>"

            if ext in saturated_exts:
                continue

            counter_data = file_types[ext]
            counter_data['count'] += 1

            # --- 统一的、基于 max_count 的显示逻辑 ---
            is_summary_active = force_summary or info['force_summary']
            
            # 计算当前模式下，此文件类型应该显示的样本数量上限
            if show_all and not is_summary_active:
                # -a 模式下，上限就是 max_count (或无限)
                display_limit = max_count if max_count > 0 else float('inf')
            else:
                # 默认或强制摘要模式下，最多只显示2个样本作为代表
                display_limit = 2
            
            # 如果当前样本数量还没达到上限，就添加
            if len(counter_data['samples']) < display_limit:
                counter_data['samples'].append(item_name)
            
            # 检查是否因为添加后达到了 max_count 的硬上限而饱和
            if max_count > 0 and counter_data['count'] >= max_count:
                saturated_exts.add(ext)

    indent = '  ' * current_depth
    display_name = os.path.basename(directory) if current_depth > 0 else directory
    dir_count_info = f" ({len(folders)} dirs)" if folders else ""
    print(f"{indent}{Fore.BLUE}{Style.BRIGHT}{display_name}{Style.RESET_ALL}/{Fore.CYAN}{dir_count_info}{Style.RESET_ALL}")

    if file_types:
        for ext in sorted(file_types.keys()):
            count = file_types[ext]['count']
            samples = file_types[ext]['samples']

            for f in samples:
                print(f"{indent}  {Fore.GREEN}{f}{Style.RESET_ALL}")

            remaining_count = count - len(samples)
            if remaining_count > 0:
                summary_color = Fore.RED + Style.BRIGHT if max_count > 0 and count >= max_count else Fore.YELLOW
                print(f"{indent}  {summary_color}... ({remaining_count} more {ext} files){Style.RESET_ALL}")

    if current_depth < max_depth - 1:
        for folder_info in folders:
            new_force_summary = force_summary or folder_info['force_summary']
            tree(os.path.join(directory, folder_info['name']), max_depth, show_all, include_patterns, combined_ignore_list, max_count, new_force_summary, current_depth + 1)

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
        result = {'name': item, 'status': '', 'color': '', 'reason': '', 'summary': ''}
        isVisible, forceSummary = get_item_final_state(item, target_path, args.include_patterns, combined_ignore_list)
        result['is_visible'] = isVisible
        result['summary'] = '(摘要)' if forceSummary else ''
        result['color'] = Fore.GREEN if isVisible else Fore.RED
        result['status'] = '[可见]' if isVisible else '[忽略]'
        full_path_for_match = os.path.join(target_path, item).replace('\\', '/')
        if any(fnmatch.fnmatch(item, p) or fnmatch.fnmatch(full_path_for_match, p) for p in args.include_patterns):
            result['reason'] = '-i 参数'
        elif any(fnmatch.fnmatch(item, p) for p, v, s in SPECIAL_HANDLING_RULES):
            result['reason'] = '特殊规则'
        elif any(fnmatch.fnmatch(item, p) or fnmatch.fnmatch(full_path_for_match, p) for p in combined_ignore_list):
            result['reason'] = '.gitignore/内置'
        else:
            result['reason'] = '默认'
        analysis_results.append(result)

    print(f"{Fore.CYAN}--- 分析模式: {target_path} ---{Style.RESET_ALL}")
    gitignore_rules = load_gitignore_rules(target_path)
    if gitignore_rules:
        print(f"{Fore.YELLOW}[规则来源]{Style.RESET_ALL} .gitignore: {len(gitignore_rules)} 条, 内置: {len(BUILTIN_IGNORE_PATTERNS)} 条 (组合使用)")
    else:
        print(f"{Fore.YELLOW}[规则来源]{Style.RESET_ALL} .gitignore: 未找到, 内置: {len(BUILTIN_IGNORE_PATTERNS)} 条 (使用内置)")
    visible_count = sum(1 for r in analysis_results if r['is_visible'])
    ignored_items = [r['name'] for r in analysis_results if not r['is_visible']]
    ignored_count = len(ignored_items)
    ignored_names_str = f" ({', '.join(ignored_items[:5])}{', ...' if len(ignored_items) > 5 else ''})" if ignored_items else ""
    print(f"{Fore.YELLOW}[一级条目]{Style.RESET_ALL} 总数: {len(raw_items)}, 可见: {visible_count}, 忽略: {ignored_count}{ignored_names_str}")
    print(f"{Fore.CYAN}{'-'*70}{Style.RESET_ALL}")
    for res in sorted(analysis_results, key=lambda x: (not x['is_visible'], x['name'].lower())):
        print(f"  {res['color']}{res['name']:<30}{res['status']:<8}{Style.RESET_ALL}{Fore.YELLOW}{res['summary']:<8}{Style.RESET_ALL}(来源: {res['reason']})")


def main():
    parser = argparse.ArgumentParser(
        description='彩色目录树生成器。\n规则优先级: --include > 特殊规则 > .gitignore + 内置规则。',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="示例: \n  ctr -l 3                       # 显示3层目录树\n  ctr -a -i data *.log           # 显示全部文件，并强制摘要data和log\n  ctr --log                      # 分析当前目录的规则应用情况\n  ctr --max_count 100            # 将文件计数上限设为100"
    )
    parser.add_argument('path', nargs='?', default=os.getcwd(), help='指定路径，默认当前目录')
    parser.add_argument('-l', '--level', type=int, default=5, help='显示的层级数目，默认是5')
    parser.add_argument('-a', '--all', action='store_true', help='显示所有文件（可被摘要规则覆盖）')
    parser.add_argument('-i', '--include', nargs='+', dest='include_patterns', default=[], help='最高优先级：强制包含一个或多个模式并启用摘要输出。\n可一次性提供多个值 (e.g., -i data *.log)。')
    parser.add_argument('--log', action='store_true', help='【分析模式】不显示目录树，仅输出规则和顶层目录的分析日志。')
    parser.add_argument('--max_count', type=int, default=500, help='摘要中文件计数的硬性统计上限，同时也是-a模式下显示的样本上限。达到上限的摘要将用红色标出。设置为0则无限制。默认为500。')

    args = parser.parse_args()

    if args.level < 1:
        print(f"{Fore.RED}错误：层级数必须大于等于1")
        sys.exit(1)

    target_path = os.path.abspath(args.path)
    combined_ignore_list = BUILTIN_IGNORE_PATTERNS + load_gitignore_rules(target_path)

    if args.log:
        run_log_mode(args, combined_ignore_list)
    else:
        try:
            tree(target_path, args.level, args.all, args.include_patterns, combined_ignore_list, args.max_count)
        except Exception as e:
            print(f"{Fore.RED}错误: {e}")

if __name__ == '__main__':
    main()
