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

PRIMARY_CODES = ["72-314", "72-476", "72-488"]
PRIMARY_NAMES = ["BS", "GH", "Cortisl"]
OPTIONAL_CODES = ["72-393", "72-481", "72-482", "72-483", "72-491", "72-484"]
OPTIONAL_NAMES = ["TSH", "PRL", "LH", "FSH", "Testosterone", "E2"]

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
    dt_pairs = []
    for i in range(len(date_lines)-1):
        date = date_lines[i].split('\t')[-1]
        time = date_lines[i+1].split('\t')[0]
        dt_pairs.append((date, time))
    all_items = {}
    code_to_name = {}
    name_to_code = {}
    code_values = {}
    for line in lines[start:]:
        parts = line.split('\t')
        if len(parts) < 5 or parts[0] != 'True':
            continue
        code = parts[1]
        name = parts[2]
        values = [re.sub(r"([\d.]+)\s*[LH]$", r"\1", v.strip()) if v.strip() else "" for v in parts[4:]]
        all_items[name] = values
        code_to_name[code] = name
        name_to_code[name] = code
        code_values[code] = values
    # 只用三個主項目決定 index
    indices_list = []
    for code in PRIMARY_CODES:
        v = code_values.get(code, [])
        indices = [i for i, val in enumerate(v) if val]
        indices_list.append(indices)
    if not indices_list or any(len(idx) == 0 for idx in indices_list):
        return {}, all_items, dt_pairs, []
    common = set(indices_list[0])
    for idxs in indices_list[1:]:
        common = common & set(idxs)
    common = sorted(common)
    seven_indices = common[:7] if len(common) >= 7 else []
    items = {}
    if seven_indices:
        seven_indices = list(reversed(seven_indices))
        # 主項目一定有
        for code, tname in zip(PRIMARY_CODES, PRIMARY_NAMES):
            v = code_values.get(code, [])
            items[tname] = [v[i] if i < len(v) else "--" for i in seven_indices]
        # 其他項目有值才顯示
        for code, tname in zip(OPTIONAL_CODES, OPTIONAL_NAMES):
            v = code_values.get(code, [])
            vals = [v[i] if i < len(v) else "" for i in seven_indices]
            if any(val for val in vals):
                # Testosterone 只顯示第一與最後一個 index
                if code == "72-491":
                    t_row = [vals[0]] + ["--"]*5 + [vals[-1]]
                    items[tname] = t_row
                else:
                    items[tname] = vals
    else:
        for tname in PRIMARY_NAMES:
            items[tname] = ["--"]*7
    return items, all_items, dt_pairs, seven_indices

def get_same_day_lab_table(lines, target_date, exclude_codes=None):
    # 取得所有檢驗項目（同一天）
    start = 0
    for idx, line in enumerate(lines):
        if '\t單位\t參考值' in line:
            start = idx+1
            break
    lab_rows = []
    for line in lines[start:]:
        parts = line.split('\t')
        if len(parts) < 6 or parts[0] != 'True':
            continue
        # 只保留檢體別為B
        if parts[3] != 'B':
            continue
        code = parts[1]
        name = parts[2]
        unit = parts[-2]
        ref = parts[-1]
        # 取出所有時間點的值
        values = parts[4:]
        # 只抓與 target_date 相同的欄位
        for idx, v in enumerate(values):
            v = v.strip()
            if not v:
                continue
            # 嘗試從 date_lines 取得日期
            date_lines = []
            for l in lines:
                if '\t單位\t參考值' in l:
                    break
                date_lines.append(l)
            dt = ''
            if idx < len(date_lines)-1:
                dt = date_lines[idx].split('\t')[-1]
            if dt == target_date:
                lab_rows.append((code, name, v, unit, ref))
    # 排除主表格已出現的項目（primary+optional codes）
    if exclude_codes is not None:
        from itertools import chain
        all_exclude = set(chain(PRIMARY_CODES, OPTIONAL_CODES))
        if isinstance(exclude_codes, list):
            all_exclude.update(exclude_codes)
        lab_rows = [row for row in lab_rows if row[0] not in all_exclude]
    # 依檢驗代號排序
    lab_rows.sort(key=lambda x: x[0])
    # 產生表格文字
    output = io.StringIO()
    
    print("\n檢驗項目\t檢驗值\t單位\t參考值", file=output)
    print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
    for row in lab_rows:
        print("\t".join(row[1:]), file=output)
    print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
    return output.getvalue() if lab_rows else "\n"

def convert_lab_text_common_seven_anywhere(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    items, all_items, dt_pairs, seven_indices = parse_items_common_seven_anywhere(lines)
    # 日期格式：以七個index中最早的日期為主
    date_fmt = ""
    target_date = ""
    if seven_indices and dt_pairs:
        dates = [dt_pairs[i][0] for i in seven_indices if i < len(dt_pairs)]
        if dates:
            min_date = min(dates)
            date_fmt = f"{min_date[:4]}/{min_date[4:6]}/{min_date[6:]}"
            target_date = min_date
    if not date_fmt:
        date_match = re.search(r"(2025[0-9]{4})", " ".join(lines))
        date_str = date_match.group(1) if date_match else "20250708"
        date_fmt = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
        target_date = date_str
    output = io.StringIO()
    # 動態產生欄位
    col_names = list(items.keys())
    # 時間欄
    print(f"＝ Insulin/TRH/GnRH test on {date_fmt} ＝\n", file=output)
    print("\t".join([""] + col_names), file=output)
    # 單位
    unit_map = {"BS": "mg/dL", "GH": "ng/mL", "Cortisl": "ug/dL", "TSH": "uIU/mL", "PRL": "ng/mL", "LH": "mIU/mL", "FSH": "mIU/mL", "Testosterone": "ng/mL", "E2": "pg/mL"}
    print("\t".join(["時間(分)"] + [unit_map.get(n, "") for n in col_names]), file=output)
    print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
    table_rows = []
    for i, label in enumerate(FIXED_TIME_LABELS):
        row = [label]
        for n in col_names:
            row.append(items.get(n, ["--"]*7)[i])
        print("\t".join([str(x) for x in row]), file=output)
        table_rows.append(row)
    print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
    # 產生同日檢驗項目表格（排除主表格項目）
    print(get_same_day_lab_table(lines, target_date, exclude_codes=list(items.keys())), file=output)
    columns = ["時間(分)"] + list(items.keys())
    df = pd.DataFrame.from_records(table_rows, columns=columns)
    full_df = pd.DataFrame.from_dict(all_items, orient='index')
    full_df.index.name = '檢驗項目'
    return output.getvalue(), df, full_df

# 頁面切換（改用 tabs）
tabs = st.tabs(["Insulin/TRH/GnRH test", "Clonidine test", "GnRH stimulation test"])

with tabs[0]:
    st.title("Insulin/TRH/GnRH test")
    input_text = st.text_area("貼上原始data：", height=300)
    if st.button("產生病歷格式", key="insulin_btn"):
        if input_text.strip():
            result, df, full_df = convert_lab_text_common_seven_anywhere(input_text)
            # 判斷主表格是否完全沒有數值
            df_check = df.replace('--', '').replace('', float('nan')).drop('時間(分)', axis=1)
            all_empty = df_check.isna().values.all()
            if all_empty:
                st.warning("⚠️ 無法擷取任何數值，可能檢驗格式有錯，或是沒有做過此項檢查。")
            else:
                st.text_area("病歷：", result, height=300)
                st.dataframe(df, use_container_width=True)
                st.write("完整表格（所有檢驗項目 x 所有時間點）：")
                st.dataframe(full_df, use_container_width=True)
                st.download_button("下載報表文字檔", result, file_name="converted_report.txt")
        else:
            st.warning("請先貼上原始data！")

with tabs[1]:
    st.title("Clonidine test")
    input_text = st.text_area("貼上原始data：", key="clonidine_input", height=300)
    if st.button("產生病歷格式", key="clonidine_btn"):
        if input_text.strip():
            def parse_clonidine_gh_five(lines):
                start = 0
                for idx, line in enumerate(lines):
                    if '\t單位\t參考值' in line:
                        start = idx+1
                        break
                gh_values = []
                for line in lines[start:]:
                    parts = line.split('\t')
                    if len(parts) < 5 or parts[0] != 'True':
                        continue
                    code = parts[1]
                    name = parts[2]
                    if code == "72-476" or name == "GH":
                        values = [v.strip() for v in parts[4:] if v.strip()]
                        gh_values.extend(values)
                gh_values = gh_values[:5] if len(gh_values) >= 5 else gh_values + ["--"]*(5-len(gh_values))
                gh_values = gh_values[::-1]  # 反轉順序，讓0'對應最後一個值
                return gh_values
            def convert_clonidine_lab_text(text):
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                gh_values = parse_clonidine_gh_five(lines)
                # 取得日期
                date_match = re.search(r"(2025[0-9]{4})", " ".join(lines))
                date_str = date_match.group(1) if date_match else "20250708"
                date_fmt = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
                target_date = date_str
                time_labels = ["0'", "30'", "60'", "90'", "120'"]
                output = io.StringIO()
                print(f"＝ Clonidine test on {date_fmt} ＝\n", file=output)
                print("\t".join(["", "GH"]), file=output)
                print("\t".join(["時間(分)", "ng/mL"]), file=output)
                print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
                table_rows = []
                for i, label in enumerate(time_labels):
                    row = [label, gh_values[i] if i < len(gh_values) else "--"]
                    print("\t".join([str(x) for x in row]), file=output)
                    table_rows.append(row)
                print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
                # 產生同日檢驗項目表格（排除主表格項目）
                print(get_same_day_lab_table(lines, target_date, exclude_codes=["72-476"]), file=output)
                df = pd.DataFrame.from_records(table_rows, columns=["時間(分)", "GH"])
                return output.getvalue(), df
            result, df = convert_clonidine_lab_text(input_text)
            # 判斷主表格是否完全沒有數值
            df_check = df.replace('--', '').replace('', float('nan')).drop('時間(分)', axis=1)
            all_empty = df_check.isna().values.all()
            if all_empty:
                st.warning("⚠️ 無法擷取任何數值，可能檢驗格式有錯，或是沒有做過此項檢查。")
            else:
                st.text_area("病歷：", result, height=200)
                st.dataframe(df, use_container_width=True)
                st.download_button("下載報表文字檔", result, file_name="clonidine_report.txt")
        else:
            st.warning("請先貼上原始data！")

with tabs[2]:
    st.title("GnRH stimulation test")
    input_text = st.text_area("貼上原始data：", key="gnrh_input", height=300)
    if st.button("產生病歷格式", key="gnrh_btn"):
        if input_text.strip():
            def parse_gnrh_lh_fsh_five(lines, target_date):
                start = 0
                for idx, line in enumerate(lines):
                    if '\t單位\t參考值' in line:
                        start = idx+1
                        break
                code_map = {"LH": "72-482", "FSH": "72-483", "Testosterone": "72-491", "E2": "72-484"}
                date_lines = []
                for l in lines:
                    if '\t單位\t參考值' in l:
                        break
                    date_lines.append(l)
                lh_list, fsh_list, test_list, e2_list = [], [], [], []
                for line in lines[start:]:
                    parts = line.split('\t')
                    if len(parts) < 6 or parts[0] != 'True':
                        continue
                    code = parts[1]
                    name = parts[2]
                    values = parts[4:]
                    for idx, v in enumerate(values):
                        v = v.strip()
                        if not v:
                            continue
                        dt = ''
                        if idx < len(date_lines)-1:
                            dt = date_lines[idx].split('\t')[-1]
                        if dt != target_date:
                            continue
                        if code == "72-482":
                            lh_list.append((idx, v))
                        elif code == "72-483":
                            fsh_list.append((idx, v))
                        elif code == "72-491":
                            test_list.append((idx, v))
                        elif code == "72-484":
                            e2_list.append((idx, v))
                lh_idx = set(i for i, _ in lh_list)
                fsh_idx = set(i for i, _ in fsh_list)
                common_idx = sorted(lh_idx & fsh_idx)
                # 只取最後五個index，並反轉順序（0' 對應最新，120' 對應最舊）
                common_idx = list(reversed(sorted(common_idx[-5:])))
                # 依 index 取值，補 --
                lh_vals = [next((v for i2, v in lh_list if i2 == i), "--") for i in common_idx]
                fsh_vals = [next((v for i2, v in fsh_list if i2 == i), "--") for i in common_idx]
                # E2、Testosterone 只顯示第一、第五筆
                def pick_first_last(vals):
                    if not common_idx:
                        return ["--"]*5
                    val_map = {i: v for i, v in vals}
                    first = val_map.get(common_idx[0], "--")
                    last = val_map.get(common_idx[-1], "--")
                    return [first] + ["--"]*3 + [last]
                test_vals = pick_first_last(test_list) if test_list else None
                e2_vals = pick_first_last(e2_list) if e2_list else None
                result = {
                    "LH": lh_vals + ["--"]*(5-len(lh_vals)),
                    "FSH": fsh_vals + ["--"]*(5-len(fsh_vals)),
                }
                if test_vals and (test_vals[0] != "--" or test_vals[4] != "--"):
                    result["Testosterone"] = test_vals
                if e2_vals and (e2_vals[0] != "--" or e2_vals[4] != "--"):
                    result["E2"] = e2_vals
                used_codes = ["72-482", "72-483", "72-491", "72-484"]
                return result, common_idx, used_codes
            def convert_gnrh_lab_text(text):
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                # 取得日期
                date_match = re.search(r"(2025[0-9]{4})", " ".join(lines))
                date_str = date_match.group(1) if date_match else "20250708"
                date_fmt = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
                target_date = date_str
                result, indices, used_codes = parse_gnrh_lh_fsh_five(lines, target_date)
                time_labels = ["0'", "30'", "60'", "90'", "120'"][:len(indices)]
                output = io.StringIO()
                col_names = list(result.keys())
                unit_map = {"LH": "mIU/mL", "FSH": "mIU/mL", "Testosterone": "ng/mL", "E2": "pg/mL"}
                print(f"＝ GnRH stimulation test on {date_fmt} ＝\n", file=output)
                print("\t".join(["" ] + col_names), file=output)
                print("\t".join(["時間(分)"] + [unit_map.get(n, "") for n in col_names]), file=output)
                print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
                table_rows = []
                for i, label in enumerate(time_labels):
                    row = [label]
                    for n in col_names:
                        row.append(result.get(n, ["--"]*len(indices))[i])
                    print("\t".join([str(x) for x in row]), file=output)
                    table_rows.append(row)
                print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
                # 計算 LH peak, FSH peak, ratio
                def get_peak(vals):
                    try:
                        vals_num = []
                        for x in vals:
                            if x in ["--", "", None]:
                                continue
                            x = x.strip()
                            # 將 <0.3 這種格式轉成 0.3
                            m = re.match(r"^<\s*(\d+(?:\.\d+)?)$", x)
                            if m:
                                x_clean = m.group(1)
                            else:
                                x_clean = x
                            vals_num.append(float(x_clean))
                        return max(vals_num) if vals_num else "--"
                    except Exception as e:
                        return "--"
                lh_peak = get_peak(result.get("LH", []))
                fsh_peak = get_peak(result.get("FSH", []))
                if isinstance(lh_peak, float) and isinstance(fsh_peak, float) and fsh_peak != 0:
                    ratio = round(lh_peak / fsh_peak, 2)
                else:
                    ratio = "--"
                print(f"\n- LH peak: {lh_peak}", file=output)
                print(f"- FSH peak: {fsh_peak}", file=output)
                print(f"- peak LH/FSH ratio: {ratio}", file=output)
                df = pd.DataFrame.from_records(table_rows, columns=["時間(分)"] + col_names)
                return output.getvalue(), df, lh_peak, fsh_peak, ratio
            result, df, lh_peak, fsh_peak, ratio = convert_gnrh_lab_text(input_text)
            # 判斷主表格是否完全沒有數值
            df_check = df.replace('--', '').replace('', float('nan')).drop('時間(分)', axis=1)
            all_empty = df_check.isna().values.all()
            if all_empty:
                st.warning("⚠️ 無法擷取任何數值，可能檢驗格式有錯，或是沒有做過此項檢查。")
            else:
                st.text_area("病歷：", result, height=200)
                st.dataframe(df, use_container_width=True)
                st.markdown(f"**LH peak:** {lh_peak}  ")
                st.markdown(f"**FSH peak:** {fsh_peak}  ")
                st.markdown(f"**LH/FSH ratio:** {ratio}")
                st.download_button("下載報表文字檔", result, file_name="gnrh_report.txt")
        else:
            st.warning("請先貼上原始data！")

