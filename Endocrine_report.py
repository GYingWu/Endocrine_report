import streamlit as st
import re
import io
import pandas as pd

# 目標項目與對應名稱
TARGETS = [
    ("72-314", "BS"),
    ("72-476", "GH"),
    ("72-488", "Cortisl"),
    ("72-393", "TSH"),
    ("72-481", "PRL"),
    ("72-482", "LH"),
    ("72-483", "FSH"),
    ("72-491", "Testosterone"),
]

# 固定時間標籤
FIXED_TIME_LABELS = ["-1(分)", "15(分)", "30(分)", "45(分)", "60(分)", "90(分)", "120(分)"]

# 解析檢驗項目，並找出所有目標項目同時有值的七個index（不要求連續）
def parse_items_common_seven_anywhere(lines):
    start = 0
    for idx, line in enumerate(lines):
        if '\t單位\t參考值' in line:
            start = idx+1
            break
    # 取得日期時間對應表
    date_lines = []
    for line in lines:
        if '\t單位\t參考值' in line:
            break
        date_lines.append(line)
    # 每一行的最後一個欄位是日期，下一行的第一個欄位是時間
    dt_pairs = []
    for i in range(len(date_lines)-1):
        date = date_lines[i].split('\t')[-1]
        time = date_lines[i+1].split('\t')[0]
        dt_pairs.append((date, time))
    all_items = {}
    target_values = {}
    testosterone_values = None
    for line in lines[start:]:
        parts = line.split('\t')
        if len(parts) < 5 or parts[0] != 'True':
            continue
        code = parts[1]
        name = parts[2]
        values = [re.sub(r"([\d.]+)\s*[LH]$", r"\1", v.strip()) if v.strip() else "" for v in parts[4:]]
        all_items[name] = values
        for tcode, tname in TARGETS:
            if code == tcode and tname != "Testosterone":
                target_values[tname] = values
            if code == "72-491" and tname == "Testosterone":
                testosterone_values = values
    indices_list = []
    for v in target_values.values():
        indices = [i for i, val in enumerate(v) if val]
        indices_list.append(indices)
    if not indices_list:
        return {}, all_items, dt_pairs, []
    common = set(indices_list[0])
    for idxs in indices_list[1:]:
        common = common & set(idxs)
    common = sorted(common)
    seven_indices = common[:7] if len(common) >= 7 else []
    items = {}
    if seven_indices:
        seven_indices = list(reversed(seven_indices))
        for tname in [t for _, t in TARGETS if t != "Testosterone"]:
            items[tname] = [target_values[tname][i] if i < len(target_values[tname]) else "--" for i in seven_indices]
        if testosterone_values:
            t_row = [testosterone_values[seven_indices[0]]] + ["--"]*5 + [testosterone_values[seven_indices[-1]]]
            items["Testosterone"] = t_row
        else:
            items["Testosterone"] = ["--"]*7
    else:
        for tname in [t for _, t in TARGETS]:
            items[tname] = ["--"]*7
    return items, all_items, dt_pairs, seven_indices

def convert_lab_text_common_seven_anywhere(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    items, all_items, dt_pairs, seven_indices = parse_items_common_seven_anywhere(lines)
    # 日期格式：以七個index中最早的日期為主
    date_fmt = ""
    if seven_indices and dt_pairs:
        # 取七個index中最早的日期
        dates = [dt_pairs[i][0] for i in seven_indices if i < len(dt_pairs)]
        if dates:
            min_date = min(dates)
            date_fmt = f"{min_date[:4]}/{min_date[4:6]}/{min_date[6:]}"
    if not date_fmt:
        # fallback: 取最前面出現的8碼數字
        date_match = re.search(r"(2025[0-9]{4})", " ".join(lines))
        date_str = date_match.group(1) if date_match else "20250708"
        date_fmt = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
    output = io.StringIO()
    print(f"＝ Insulin/TRH/GnRH test on {date_fmt} ＝\n", file=output)
    print("\t".join(["", "BS", "GH", "Cortisl", "TSH", "PRL", "LH", "FSH", "Testosterone"]), file=output)
    print("\t".join(["時間(分)", "mg/dL", "ng/mL", "ug/dL", "uIU/mL", "ng/mL", "mIU/mL", "mIU/mL", "ng/mL"]), file=output)
    print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
    table_rows = []
    for i, label in enumerate(FIXED_TIME_LABELS):
        row = [label]
        for _, tname in TARGETS:
            row.append(items.get(tname, ["--"]*7)[i])
        print("\t".join([str(x) for x in row]), file=output)
        table_rows.append(row)
    print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
    columns = ["時間(分)"] + [tname for _, tname in TARGETS]
    df = pd.DataFrame.from_records(table_rows, columns=columns)
    full_df = pd.DataFrame.from_dict(all_items, orient='index')
    full_df.index.name = '檢驗項目'
    return output.getvalue(), df, full_df

st.title("Insulin/TRH/GnRH test")

input_text = st.text_area("貼上原始data：", height=300)

if st.button("產生病歷格式"):
    if input_text.strip():
        result, df, full_df = convert_lab_text_common_seven_anywhere(input_text)
        st.text_area("病歷：", result, height=300)
        st.dataframe(df, use_container_width=True)
        st.write("完整表格（所有檢驗項目 x 所有時間點）：")
        st.dataframe(full_df, use_container_width=True)
        st.download_button("下載報表文字檔", result, file_name="converted_report.txt")
    else:
        st.warning("請先貼上原始data！") 