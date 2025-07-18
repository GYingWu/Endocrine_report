import streamlit as st
import re
import io
import pandas as pd

st.set_page_config(layout="centered")

# 目標項目與對應名稱
PRIMARY_CODES = ["72-314", "72-476", "72-488"]
PRIMARY_NAMES = ["BS", "GH", "Cortisl"]
OPTIONAL_CODES = ["72-393", "72-481", "72-482", "72-483", "72-491", "72-484", "72-487"]
OPTIONAL_NAMES = ["TSH", "PRL", "LH", "FSH", "Testost", "E2", "ACTH"]

# 固定時間標籤
FIXED_TIME_LABELS = ["-1(分)", "15(分)", "30(分)", "45(分)", "60(分)", "90(分)", "120(分)"]

# 定義全域 clean_val 函式
def clean_val(v):
    v = re.sub(r"<\s+(\d+(?:\.\d+)?)", r"<\1", v)
    v = re.sub(r"([\d.]+)\s*[LH]$", r"\1", v)
    return v

# 解析檢驗項目，並找出所有目標項目同時有值的七個index（不要求連續）
def parse_items_common_seven_anywhere(lines):
    single_value_optional_codes = set()
    main_table_codes = set(PRIMARY_CODES)
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
    # 新增：補最後一個日期與時間
    if len(date_lines) >= 2:
        last_date = date_lines[-1].split('\t')[-1]
        last_time = date_lines[-1].split('\t')[0]
        dt_pairs.append((last_date, last_time))
    all_items = {}
    code_values = {}
    for line in lines[start:]:
        parts = line.split('\t')
        if len(parts) < 5 or parts[0] != 'True':
            continue
        code = parts[1]
        name = parts[2]
        # 只處理72-300以上的代碼
        if not (code.startswith('72-') and code[3:].isdigit() and int(code[3:]) >= 300):
            continue
        values = [clean_val(v.strip()) if v.strip() else "" for v in parts[4:-2]]
        all_items[name] = values
        code_values[code] = values
    # 依據 dt_pairs 對應每一個數值的日期
    # 找出三個主項目各自有7筆的日期
    date_indices = {code: {} for code in PRIMARY_CODES}
    for code in PRIMARY_CODES:
        v = code_values.get(code, [])
        for i, val in enumerate(v):
            if val and i < len(dt_pairs):
                d = dt_pairs[i][0]
                date_indices[code].setdefault(d, []).append(i)
    # 找出同時有7個值的日期
    candidate_dates = []
    for d in set.intersection(*(set(date_indices[code].keys()) for code in PRIMARY_CODES)):
        if all(len(date_indices[code][d]) >= 7 for code in PRIMARY_CODES):
            candidate_dates.append(d)
    if not candidate_dates:
        return {}, all_items, dt_pairs, [], set(), set()
    # 取最新的日期
    target_date = sorted(candidate_dates)[-1]
    items = {}
    # 主項目（BS、GH、Cortisol）各自依index由大到小排序，取7個值
    for code, tname in zip(PRIMARY_CODES, PRIMARY_NAMES):
        indices = sorted(date_indices[code][target_date], reverse=True)
        v = code_values.get(code, [])
        items[tname] = [v[i] for i in indices]
    # 其他項目有值才顯示，index 以主項目 index 為主
    for code, tname in zip(OPTIONAL_CODES, OPTIONAL_NAMES):
        v = code_values.get(code, [])
        vals = [v[i] if i < len(v) and v[i] else "--" for i in range(7)]
        if sum(1 for val in vals if val != "--") <= 1:
            single_value_optional_codes.add(code)
            continue
        if any(val for val in vals if val != "--"):
            main_table_codes.add(code)
            items[tname] = vals
    return items, all_items, dt_pairs, list(range(7)), single_value_optional_codes, main_table_codes

def get_same_day_lab_table(lines, target_date, exclude_codes=None):
    # 取得所有檢驗項目（同一天）
    start = 0
    for idx, line in enumerate(lines):
        if '\t單位\t參考值' in line:
            start = idx+1
            break
    # 產生 date_lines，對應數值欄位的日期
    date_lines = []
    for line in lines:
        if '\t單位\t參考值' in line:
            break
        date_lines.append(line)
    lab_rows = []
    for line in lines[start:]:
        parts = line.split('\t')
        if len(parts) < 6 or parts[0] != 'True':
            continue
        if parts[3] != 'B':
            continue
        code = parts[1]
        # 只處理72-300以上的代碼
        if not (code.startswith('72-') and code[3:].isdigit() and int(code[3:]) >= 300):
            continue
        name = parts[2]
        unit = parts[-2]
        ref = parts[-1]
        values = [clean_val(v.strip()) if v.strip() else "" for v in parts[4:-2]]  # 只抓數值欄位
        # 補齊 date_lines 長度
        while len(date_lines) < len(values):
            date_lines.append(date_lines[-1])
        for idx, v in enumerate(values):
            v = v.strip()
            if not v:
                continue
            dt = ''
            if idx < len(date_lines):
                dt = date_lines[idx].split('\t')[-1]
            if dt == target_date:
                # 移除數值結尾的 L 或 H
                v_clean = clean_val(v)
                lab_rows.append((code, name, v_clean, unit, ref))
    # 排除主表格已出現的項目（primary+optional codes）
    if exclude_codes is not None:
        all_exclude = set(exclude_codes)
        all_exclude.add("72-48A")  # 額外排除 72-48A
        lab_rows = [row for row in lab_rows if row[0] not in all_exclude]
    lab_rows.sort(key=lambda x: x[0])
    output = io.StringIO()
    # 下方表格（get_same_day_lab_table）
    print("\n檢驗項目\t檢驗值\t單位\t參考值", file=output)
    print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
    for row in lab_rows:
        print("\t".join([row[1][:7]] + list(row[2:])), file=output)
    print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
    return output.getvalue() if lab_rows else "\n"

# 修改 convert_lab_text_common_seven_anywhere 支援 time_labels 參數
def convert_lab_text_common_seven_anywhere(text, time_labels=None, glucagon_title=False):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    items, all_items, dt_pairs, seven_indices, single_value_optional_codes, main_table_codes = parse_items_common_seven_anywhere(lines)
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
    col_names = [n[:7] for n in items.keys()]
    # 時間欄
    if glucagon_title:
        print(f"＝ Glucagon test for GH stimulation on {date_fmt} ＝\n", file=output)
    else:
        print(f"＝ Insulin/TRH/GnRH test on {date_fmt} ＝\n", file=output)
    print("\t".join([""] + col_names), file=output)
    # 單位
    unit_map = {"BS": "mg/dL", "GH": "ng/mL", "Cortisl": "ug/dL", "TSH": "uIU/mL", "PRL": "ng/mL", "LH": "mIU/mL", "FSH": "mIU/mL", "Testost": "ng/mL", "E2": "pg/mL"}
    print("\t".join(["時間(分)"] + [unit_map.get(n[:7], "") for n in items.keys()]), file=output)
    print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
    table_rows = []
    labels = time_labels if time_labels is not None else FIXED_TIME_LABELS
    for i, label in enumerate(labels):
        row = [label]
        for n in col_names:
            row.append(items.get(n, ["--"]*7)[i])
        print("\t".join([str(x) for x in row]), file=output)
        table_rows.append(row)
    print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
    # 產生同日檢驗項目表格（排除主表格項目）
    # 產生同日檢驗項目表格時，exclude_codes 只排除主表格顯示的 code
    exclude_codes = list(main_table_codes)
    print(get_same_day_lab_table(lines, target_date, exclude_codes=exclude_codes), file=output)
    columns = ["時間(分)"] + list(items.keys())
    df = pd.DataFrame.from_records(table_rows, columns=columns)
    # 產生唯一欄位名稱
    columns = []
    col_count = {}
    for dt in dt_pairs:
        col_name = f"{dt[0]} {dt[1]}"
        if col_name in col_count:
            col_count[col_name] += 1
            col_name = f"{col_name}_{col_count[col_name]}"
        else:
            col_count[col_name] = 0
        columns.append(col_name)
    full_df = pd.DataFrame.from_dict(all_items, orient='index')
    full_df.columns = columns
    full_df.index = [str(idx)[:7] for idx in full_df.index]
    full_df.index.name = '檢驗項目'
    return output.getvalue(), df, full_df

# 頁面切換（改用 tabs）
tabs = st.tabs(["Insulin/TRH/GnRH test", "Clonidine test", "GnRH stimulation test", "Glucagon test for C-peptide function"])

with tabs[0]:
    st.header("Insulin/TRH/GnRH test")
    use_glucagon_time = st.checkbox("將insulin改為glucagon")
    input_text = st.text_area("貼上原始data：", height=300)
    if st.button("產生病歷格式", key="insulin_btn"):
        if input_text.strip():
            time_labels = ["-1'", "30'", "60'", "90'", "120'", "150'", "180'"] if use_glucagon_time else FIXED_TIME_LABELS
            result, df, full_df = convert_lab_text_common_seven_anywhere(input_text, time_labels=time_labels, glucagon_title=use_glucagon_time)
            # 判斷主表格是否完全沒有數值
            df_check = df.replace('--', '').replace('', float('nan')).drop('時間(分)', axis=1)
            all_empty = df_check.isna().values.all()
            if all_empty:
                st.warning("⚠️ 無法擷取任何數值，可能檢驗格式有錯，或是沒有做過此項檢查。")
            #st.write("完整表格（所有檢驗項目 x 所有時間點）：")
            #st.dataframe(full_df, use_container_width=True)
            if not all_empty:
                st.text_area("病歷：", result, height=300)
                st.dataframe(df, use_container_width=True)
                st.download_button("下載文字檔", result, file_name="converted_report.txt")
        else:
            st.warning("請先貼上原始data！")

with tabs[1]:
    st.header("Clonidine test")
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
                        values = [clean_val(v.strip()) if v.strip() else "" for v in parts[4:]]
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
                print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
                table_rows = []
                for i, label in enumerate(time_labels):
                    row = [label, gh_values[i] if i < len(gh_values) else "--"]
                    print("\t".join([str(x) for x in row]), file=output)
                    table_rows.append(row)
                print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
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
                st.download_button("下載文字檔", result, file_name="clonidine_report.txt")
        else:
            st.warning("請先貼上原始data！")

with tabs[2]:
    st.header("GnRH stimulation test")
    input_text = st.text_area("貼上原始data：", key="gnrh_input", height=300)
    if st.button("產生病歷格式", key="gnrh_btn"):
        if input_text.strip():
            def parse_gnrh_lh_fsh_five(lines, target_date):
                start = 0
                for idx, line in enumerate(lines):
                    if '\t單位\t參考值' in line:
                        start = idx+1
                        break
                code_map = {"LH": "72-482", "FSH": "72-483", "Testost": "72-491", "E2": "72-484"}
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
                    values = [clean_val(v.strip()) if v.strip() else "" for v in parts[4:]]
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
                # 依 index 取值，補 --，並去除 H/L
                lh_map = {i: clean_val(v) for i, v in lh_list}
                fsh_map = {i: clean_val(v) for i, v in fsh_list}
                test_map = {i: clean_val(v) for i, v in test_list}
                e2_map = {i: clean_val(v) for i, v in e2_list}
                lh_vals = [lh_map.get(i, "--") for i in common_idx]
                fsh_vals = [fsh_map.get(i, "--") for i in common_idx]
                # Testosterone、E2 都根據 common_idx 填寫
                test_vals = [test_map.get(i, "--") for i in common_idx] if test_list else None
                e2_vals = [e2_map.get(i, "--") for i in common_idx] if e2_list else None
                result = {
                    "LH": lh_vals + ["--"]*(5-len(lh_vals)),
                    "FSH": fsh_vals + ["--"]*(5-len(fsh_vals)),
                }
                if test_vals and (test_vals[0] != "--" or test_vals[4] != "--"):
                    result["Testost"] = test_vals
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
                unit_map = {"LH": "mIU/mL", "FSH": "mIU/mL", "Testost": "ng/mL", "E2": "pg/mL"}
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
                st.download_button("下載文字檔", result, file_name="gnrh_report.txt")
        else:
            st.warning("請先貼上原始data！")

with tabs[3]:
    st.header("Glucagon test for C-peptide function")
    input_text = st.text_area("貼上原始data：", key="glucagon_input", height=300)
    if st.button("產生病歷格式", key="glucagon_btn"):
        if input_text.strip():
            def parse_glucagon_items(lines):
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
                code_values = {}
                for line in lines[start:]:
                    parts = line.split('\t')
                    if len(parts) < 5 or parts[0] != 'True':
                        continue
                    code = parts[1]
                    # 只處理72-300以上的代碼
                    if not (code.startswith('72-') and code[3:].isdigit() and int(code[3:]) >= 300):
                        continue
                    values = [clean_val(v.strip()) if v.strip() else "" for v in parts[4:]]
                    code_values[code] = values
                # 只用 72-314 和 72-497
                sugar_vals = code_values.get("72-314", [])
                cpep_vals = code_values.get("72-497", [])
                # 取得各自有值的 index 與日期
                sugar_idx_dates = [(i, dt_pairs[i][0]) for i, v in enumerate(sugar_vals) if v and i < len(dt_pairs)]
                cpep_idx_dates = [(i, dt_pairs[i][0]) for i, v in enumerate(cpep_vals) if v and i < len(dt_pairs)]
                # 找出同一天最多的日期（以 sugar 為主）
                from collections import Counter
                sugar_date_counter = Counter([d for i, d in sugar_idx_dates])
                cpep_date_counter = Counter([d for i, d in cpep_idx_dates])
                # 取出有四筆的日期
                sugar_target_date = next((d for d, c in sugar_date_counter.items() if c >= 4), None)
                cpep_target_date = next((d for d, c in cpep_date_counter.items() if c >= 4), None)
                # 以 sugar_target_date 為主，若沒有則用 cpep_target_date
                target_date = sugar_target_date or cpep_target_date
                # 取出該日期的 index
                sugar_indices = [i for i, d in sugar_idx_dates if d == target_date]
                cpep_indices = [i for i, d in cpep_idx_dates if d == target_date]
                # 取最新四筆 index，並由大到小
                sugar_indices = sorted(sugar_indices)[-4:][::-1] if len(sugar_indices) >= 4 else []
                cpep_indices = sorted(cpep_indices)[-4:][::-1] if len(cpep_indices) >= 4 else []
                sugar_out = [sugar_vals[i] if i < len(sugar_vals) else "--" for i in sugar_indices] if sugar_indices else ["--"]*4
                cpep_out = [cpep_vals[i] if i < len(cpep_vals) else "--" for i in cpep_indices] if cpep_indices else ["--"]*4
                return sugar_out, cpep_out
            def convert_glucagon_lab_text(text):
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                sugar_vals, cpep_vals = parse_glucagon_items(lines)
                time_labels = ["0'", "3'", "6'", "10'"]
                output = io.StringIO()
                print(f"＝ Glucagon test for C-peptide function ＝   \n", file=output)
                print("\tC-peptide\tBlood Sugar", file=output)
                print("\t(ng/mL)\t\t(mg/dL)", file=output)
                print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
                table_rows = []
                for i, label in enumerate(time_labels):
                    cpep = cpep_vals[i] if i < len(cpep_vals) else "--"
                    sugar = sugar_vals[i] if i < len(sugar_vals) else "--"
                    print(f"{label}\t{cpep}\t\t{sugar}", file=output)
                    table_rows.append([label, cpep, sugar])
                print("＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝", file=output)
                # 新增 C-peptide 指標計算
                def to_float(val):
                    try:
                        return float(val)
                    except:
                        return None
                fasting = cpep_vals[0] if len(cpep_vals) > 0 else "--"
                post6 = cpep_vals[2] if len(cpep_vals) > 2 else "--"
                cpep_floats = [to_float(x) for x in cpep_vals if to_float(x) is not None]
                cpep_floats_clean = [x for x in cpep_floats if x is not None]
                peak = max(cpep_floats_clean) if cpep_floats_clean else "--"
                fasting_float = to_float(fasting)
                delta = round(peak - fasting_float, 2) if (peak != "--" and fasting_float is not None) else "--"
                print("\nFasting C-peptide:  {} ng/mL".format(fasting), file=output)
                print("6' post-glucagon C-peptide:  {} ng/mL".format(post6), file=output)
                print("Stimulated peak C-peptide:  {} ng/mL".format(peak), file=output)
                print("ΔCP ＝  {} ng/mL".format(delta), file=output)
                df = pd.DataFrame.from_records(table_rows, columns=["時間(分)", "C-peptide", "Blood Sugar"])
                appendix = '''\
\n********************************************************************   
2022年第一型糖尿病申請全民健保重大傷病依據   
C-peptide/glucagon test(residual insulin function)(NTUH)   
   
Age(y)\t\t＞18y/o\t＜18y/o   
＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝   
Fasting C-P\t＜ 0.5\t＜ 0.5\tng/mL   
6min C-P\t＜ 1.8\t＜ 3.3\tng/mL   
ΔC-P\t\t＜ 0.7\t   X\tng/mL   
＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝   
********************************************************************   
ΔCP(increment of serum C-peptide during glucagons test)(CGMH成人新代)   
- IDDM(Insulin-Dependent Diabetes Mellitus):      ΔCP  ≦  0.69  ng/mL     
- NIDDM(Non-Insulin-Dependent Diabetes Mellitus): ΔCP  ≧  1.20  ng/mL    
     
Peak and fasting C-peptide level   
- IDDM:  peak CP ＜ 1.5 ng/dl or fasting CP ＜ 1 ng/dl   
- NIDDM: peak CP ≧ 1.5 ng/dl or fasting CP ≧ 1 ng/dl    
******************************************************************** 
'''
                return output.getvalue() + appendix, df
            result, df = convert_glucagon_lab_text(input_text)
            # 判斷主表格是否完全沒有數值
            df_check = df.replace('--', '').replace('', float('nan')).drop('時間(分)', axis=1)
            all_empty = df_check.isna().values.all()
            if all_empty:
                st.warning("⚠️ 無法擷取任何數值，可能檢驗格式有錯，或是沒有做過此項檢查。")
            else:
                st.text_area("病歷：", result, height=200)
                st.dataframe(df, use_container_width=True)
                st.download_button("下載文字檔", result, file_name="glucagon_report.txt")
        else:
            st.warning("請先貼上原始data！")

