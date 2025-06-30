import os
import sys
import argparse
from collections import defaultdict
from colorama import init, Fore, Style

# 初始化 colorama
init()

def tree(directory, max_depth, current_depth=0):
    # 获取目录中的所有项目
    try:
        items = os.listdir(directory)
    except PermissionError:
        indent = '  ' * current_depth
        print(f"{indent}{Fore.RED}Permission denied: {os.path.basename(directory)}{Style.RESET_ALL}")
        return
    except FileNotFoundError:
        indent = '  ' * current_depth
        print(f"{indent}{Fore.RED}Not found: {os.path.basename(directory)}{Style.RESET_ALL}")
        return

    # 分类文件夹和文件
    folders = []
    file_types = defaultdict(lambda: [0, []])  # [count, [sample1, sample2]]
    
    for item in items:
        full_path = os.path.join(directory, item)
        if os.path.isdir(full_path):
            folders.append(item)
        else:
            # 处理文件
            _, ext = os.path.splitext(item)
            ext = ext.lower() or ".<no ext>"
            counter_data = file_types[ext]
            counter_data[0] += 1
            if counter_data[0] <= 2:
                counter_data[1].append(item)
    
    # 仅对文件夹排序
    folders.sort()
    
    # 显示当前目录
    indent = '  ' * current_depth
    if current_depth == 0:
        print(f"{Fore.BLUE}{Style.BRIGHT}{os.path.basename(directory)}{Style.RESET_ALL}/")
    else:
        print(f"{indent}{Fore.BLUE}{Style.BRIGHT}{os.path.basename(directory)}{Style.RESET_ALL}/")
    
    # 显示文件
    if file_types:
        # 按扩展名排序
        for ext in sorted(file_types.keys()):
            count, samples = file_types[ext]
            # 显示样本文件
            for f in samples:
                print(f"{indent}  {Fore.GREEN}{f}{Style.RESET_ALL}")
            # 显示省略信息
            if count > 2:
                print(f"{indent}  {Fore.YELLOW}... ({count-2} more {ext} files){Style.RESET_ALL}")
    
    # 递归处理子目录
    if current_depth < max_depth - 1:
        for folder in folders:
            folder_path = os.path.join(directory, folder)
            tree(folder_path, max_depth, current_depth + 1)

def main():
    parser = argparse.ArgumentParser(description='彩色目录树生成器')
    parser.add_argument('path', nargs='?', default=os.getcwd(), help='指定路径，默认当前目录')
    parser.add_argument('-l', '--level', type=int, default=5, help='显示的层级数目，默认是5')
    
    args = parser.parse_args()
    
    if args.level < 1:
        print(f"{Fore.RED}错误：层级数必须大于等于1{Style.RESET_ALL}")
        sys.exit(1)
    
    try:
        tree(args.path, args.level)
    except Exception as e:
        print(f"{Fore.RED}错误: {e}{Style.RESET_ALL}")

if __name__ == '__main__':
    main()