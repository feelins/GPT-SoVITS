import csv
from collections import defaultdict

def save_two_groups_near_target_size(input_tsv, target_size=200, tolerance=10):
    groups = defaultdict(list)
    header = None

    # 读取并分组
    with open(input_tsv, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        header = next(reader)
        client_id_col = header.index('client_id')

        for row in reader:
            cid = row[client_id_col]
            groups[cid].append(row)

    # 筛选行数在 [target - tolerance, target + tolerance] 范围内的组
    lower = target_size - tolerance
    upper = target_size + tolerance
    candidates = [
        (cid, rows) for cid, rows in groups.items()
        if lower <= len(rows) <= upper
    ]

    # 按 client_id 排序（或按行数/原始顺序，这里简单按 cid）
    candidates.sort(key=lambda x: x[0])

    if len(candidates) < 2:
        print(f"⚠️ 找到 {len(candidates)} 组满足 {lower}～{upper} 行，少于2组，无法保存两组。")
        return

    # 取前两组
    for i, (cid, rows) in enumerate(candidates[:2], start=1):
        output_file = f"group_{i}_client_{cid}_{len(rows)}rows.tsv"
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter='\t')
            writer.writerow(header)
            writer.writerows(rows)
        print(f"✅ 已保存第 {i} 组: client_id={cid}, 行数={len(rows)} → {output_file}")

# 使用示例
if __name__ == "__main__":
    input_file = "/Volumes/feelins-mac/03-dataset/mcv-scripted-nan-tw-v23.0/cv-corpus-23.0-2025-09-05/nan-tw/validated.tsv"  # 替换为你的文件路径
    save_two_groups_near_target_size(
        input_tsv=input_file,
        target_size=800,
        tolerance=500   # 接受 190～210 行的组
    )