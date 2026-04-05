import csv
from collections import defaultdict

def split_top2_client_groups(input_tsv):
    groups = defaultdict(list)
    header = None

    # 第一次遍历：读取并按 client_id 分组（跳过 header）
    with open(input_tsv, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        header = next(reader)  # 读取表头
        client_id_col = header.index('client_id')

        for row in reader:
            cid = row[client_id_col]
            groups[cid].append(row)

    # 按每组的行数降序排序，取前2
    sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)
    top2 = sorted_groups[:2]

    # 分别保存前2组
    for i, (cid, rows) in enumerate(top2, start=1):
        output_file = f"top{i}_client_{cid}.tsv"
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter='\t')
            writer.writerow(header)          # 写入表头
            writer.writerows(rows)           # 写入该 client_id 的所有行
        print(f"已保存第 {i} 大组 (client_id={cid}, 共 {len(rows)} 行) 到 {output_file}")

# 使用示例
if __name__ == "__main__":
    input_file = "/Volumes/feelins-mac/03-dataset/mcv-scripted-nan-tw-v23.0/cv-corpus-23.0-2025-09-05/nan-tw/validated.tsv"  # 替换为你的输入文件路径
    split_top2_client_groups(input_file)