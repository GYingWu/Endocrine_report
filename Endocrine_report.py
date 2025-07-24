import streamlit as st
import re
import io
import pandas as pd

st.set_page_config(layout="centered")

# 目標項目與對應名稱
PRIMARY_CODES = ["72-314", "72-476", "72-488"]
PRIMARY_NAMES = ["BS", "GH", "Cortisol"]
OPTIONAL_CODES = ["72-393", "72-481", "72-482", "72-483", "72-491", "72-484", "72-487"]
OPTIONAL_NAMES = ["TSH", "PRL", "LH", "FSH", "Testosterone", "E2", "ACTH"]

# 固定時間標籤
FIXED_TIME_LABELS = ["-1'", "15'", "30'", "45'", "60'", "90'", "120'"]

# 定義全域 clean_val 函式
def clean_val(v):
    v = re.sub(r"<\s+(\d+(?:\.\d+)?)", r"<\1", v)
    v = re.sub(r"([\d.]+)\s*[LH]$", r"\1", v)
    return v

# 計算字串寬度（中文字佔2字元，其他佔1字元）
def get_string_width(s):
    """計算字串的顯示寬度，中文字佔2字元，其他佔1字元"""
    width = 0
    for char in s:
        # 檢查是否為中文字（CJK統一漢字）
        if '\u4e00' <= char <= '\u9fff':
            width += 2
        # 檢查是否為全形字元（包括希臘字母、特殊符號等）
        elif ord(char) > 127:
            # 醫院系統會把 β、=、< 等轉為全形，都算2字元
            width += 2
        else:
            # ASCII 字元，但 <、>、= 在醫院系統中會被轉為全形，所以算2字元
            if char in ['<', '>', '=']:
                width += 2
            else:
                width += 1
    return width

# 定義固定寬度格式化函式
def format_with_fixed_width(items, width=9):
    """用空格補齊到固定寬度，若文字>8字元就切掉"""
    result = []
    for item in items:
        item_str = str(item)
        # 若文字寬度>8就切掉
        if get_string_width(item_str) > 8:
            # 找到合適的切斷點
            cut_pos = 0
            current_width = 0
            for i, char in enumerate(item_str):
                char_width = 2 if ord(char) > 127 else 1
                if current_width + char_width > 8:
                    break
                current_width += char_width
                cut_pos = i + 1
            item_str = item_str[:cut_pos]
        # 用空格補齊到固定寬度
        current_width = get_string_width(item_str)
        padding = width - current_width
        padded_item = item_str + " " * padding
        result.append(padded_item)
    return "".join(result)

# 定義混合寬度格式化函式（參考值不限制）
def format_with_mixed_width(items, widths=None):
    """用不同寬度格式化，參考值不限制"""
    if widths is None:
        widths = [9, 9, 9, 0]  # 檢驗項目、檢驗值、單位、參考值（0表示不限制）
    result = []
    for i, item in enumerate(items):
        item_str = str(item)
        width = widths[i] if i < len(widths) else 9
        # 只有非參考值欄位才限制長度
        if i < 3 and get_string_width(item_str) > 8:
            # 找到合適的切斷點
            cut_pos = 0
            current_width = 0
            for j, char in enumerate(item_str):
                char_width = 2 if ord(char) > 127 else 1
                if current_width + char_width > 8:
                    break
                current_width += char_width
                cut_pos = j + 1
            item_str = item_str[:cut_pos]
        # 參考值不限制寬度，其他欄位用空格補齊
        if width == 0:  # 參考值
            padded_item = item_str
        else:
            current_width = get_string_width(item_str)
            padding = width - current_width
            padded_item = item_str + " " * padding
        result.append(padded_item)
    return "".join(result)

# 定義動態分隔線函式
def get_dynamic_separator(items, width=9):
    """根據項目數量產生對應長度的分隔線"""
    # 計算總字元數（考慮實際字元寬度）
    total_chars = 0
    for item in items:
        item_str = str(item)
        # 計算實際字元寬度
        item_width = get_string_width(item_str)
        # 補齊到指定寬度
        total_chars += max(item_width, width)
    # 因為＝字元本身佔2字元，所以分隔線長度要減半
    separator_length = max(total_chars // 2, 10)  # 最少10個字元
    return "＝" * separator_length

# 定義 glucagon test 專用的格式化函式（11字元寬度，不切文字）
def format_glucagon_width(items, width=11):
    """用空格補齊到11字元寬度，不切文字"""
    result = []
    for item in items:
        item_str = str(item)
        # 用空格補齊到固定寬度，不切文字
        current_width = get_string_width(item_str)
        padding = width - current_width
        padded_item = item_str + " " * padding
        result.append(padded_item)
    return "".join(result)

# 定義 glucagon test 專用的分隔線函式
def get_glucagon_separator(items, width=11):
    """根據項目數量產生對應長度的分隔線（glucagon test 專用）"""
    # 計算總字元數（考慮實際字元寬度）
    total_chars = 0
    for item in items:
        item_str = str(item)
        # 計算實際字元寬度
        item_width = get_string_width(item_str)
        # 補齊到指定寬度
        total_chars += max(item_width, width)
    # 因為＝字元本身佔2字元，所以分隔線長度要減半
    separator_length = max(total_chars // 2, 10)  # 最少10個字元
    return "＝" * separator_length

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
    bs_indices = sorted(date_indices[PRIMARY_CODES[0]][target_date], reverse=True)
    for code, tname in zip(PRIMARY_CODES, PRIMARY_NAMES):
        indices = sorted(date_indices[code][target_date], reverse=True)
        v = code_values.get(code, [])
        items[tname] = [v[i] for i in indices]
    # optional code 收集同一天日期下有值的 index，忽略空值
    for code, tname in zip(OPTIONAL_CODES, OPTIONAL_NAMES):
        v = code_values.get(code, [])
        # 找出該 code 在同一天日期下有值的 index
        code_indices = []
        for i, val in enumerate(v):
            if val and i < len(dt_pairs):
                d = dt_pairs[i][0]
                if d == target_date:
                    code_indices.append(i)
        # 依 index 由大到小排序
        code_indices = sorted(code_indices, reverse=True)
        # 取值
        vals = [v[i] for i in code_indices]
        # 特殊處理：testosterone 和 E2 如果有兩個值，一定要佔第一和第七位置
        if tname in ["Testosterone", "E2"] and len(vals) == 2:
            # 重新排列：第一個值放第一位置，第二個值放第七位置
            new_vals = ["--"] * 7  # 假設總共 7 個位置
            new_vals[0] = vals[0]  # 第一位置
            new_vals[6] = vals[1]  # 第七位置
            vals = new_vals
        if sum(1 for val in vals if val != "--") <= 1:
            single_value_optional_codes.add(code)
            continue
        if any(val for val in vals if val != "--"):
            main_table_codes.add(code)
            items[tname] = vals
    return items, all_items, dt_pairs, bs_indices, single_value_optional_codes, main_table_codes

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
    header_row = ["檢驗項目", "檢驗值", "單位", "參考值"]
    formatted_header = format_with_mixed_width(header_row)
    print("\n" + formatted_header, file=output)
    # 動態計算分隔線長度（包含參考值的實際寬度）
    # 前三個欄位固定寬度：9+9+9=27
    # 參考值寬度需要計算實際內容
    max_ref_width = 0
    for row in lab_rows:
        ref_width = get_string_width(str(row[4]))  # 參考值是第5個元素
        max_ref_width = max(max_ref_width, ref_width)
    total_width = 27 + max_ref_width  # 前三個欄位 + 最大參考值寬度
    # 因為＝字元本身佔2字元，所以分隔線長度要減半
    separator_length = total_width // 2
    separator = "＝" * separator_length
    print(separator, file=output)
    for row in lab_rows:
        print(format_with_mixed_width([row[1]] + list(row[2:])), file=output)
    print(separator, file=output)
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
    col_names = list(items.keys())
    # 時間欄
    if glucagon_title:
        print(f"＝ Glucagon test for GH stimulation on {date_fmt} ＝\n", file=output)
    else:
        print(f"＝ Insulin/TRH/GnRH test on {date_fmt} ＝\n", file=output)
    print(format_with_fixed_width([""] + col_names), file=output)
    # 單位
    unit_map = {"BS": "mg/dL", "GH": "ng/mL", "Cortisol": "ug/dL", "TSH": "uIU/mL", "PRL": "ng/mL", "LH": "mIU/mL", "FSH": "mIU/mL", "Testosterone": "ng/mL", "E2": "pg/mL"}
    header_row = ["時間"] + [unit_map.get(n, "") for n in items.keys()]
    print(format_with_fixed_width(header_row), file=output)
    separator = get_dynamic_separator(header_row)
    print(separator, file=output)
    table_rows = []
    labels = time_labels if time_labels is not None else FIXED_TIME_LABELS
    for i, label in enumerate(labels):
        row = [label]
        for n in col_names:
            item_data = items.get(n, [])
            if i < len(item_data):
                row.append(item_data[i])
            else:
                row.append("--")
        print(format_with_fixed_width(row), file=output)
        table_rows.append(row)
    print(separator, file=output)
    # 產生同日檢驗項目表格（排除主表格項目）
    # 產生同日檢驗項目表格時，exclude_codes 只排除主表格顯示的 code
    exclude_codes = list(main_table_codes)
    print(get_same_day_lab_table(lines, target_date, exclude_codes=exclude_codes), file=output)
    columns = ["時間"] + list(items.keys())
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
            df_check = df.replace('--', '').replace('', float('nan')).drop('時間', axis=1)
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
                # 補最後一組
                if len(date_lines) >= 2:
                    last_date = date_lines[-1].split('\t')[-1]
                    last_time = date_lines[-1].split('\t')[0]
                    dt_pairs.append((last_date, last_time))
                
                # 收集所有檢驗項目的資料
                all_data = {}
                for line in lines[start:]:
                    parts = line.split('\t')
                    if len(parts) < 5 or parts[0] != 'True':
                        continue
                    code = parts[1]
                    name = parts[2]
                    values = [clean_val(v.strip()) if v.strip() else "" for v in parts[4:]]
                    all_data[code] = values
                
                # 找出有5項GH數值且沒有cortisol的日期
                target_date = None
                gh_values = []
                
                # 檢查每個日期
                for date in set(dt_pairs[i][0] for i in range(len(dt_pairs))):
                    # 檢查該日期是否有cortisol
                    has_cortisol = False
                    if "72-488" in all_data:  # cortisol的代碼
                        cortisol_values = all_data["72-488"]
                        for i, val in enumerate(cortisol_values):
                            if val and i < len(dt_pairs) and dt_pairs[i][0] == date:
                                has_cortisol = True
                                break
                    
                    if has_cortisol:
                        continue  # 跳過有cortisol的日期
                    
                    # 檢查該日期的GH數值
                    if "72-476" in all_data:  # GH的代碼
                        gh_data = all_data["72-476"]
                        date_gh_values = []
                        for i, val in enumerate(gh_data):
                            if val and i < len(dt_pairs) and dt_pairs[i][0] == date:
                                date_gh_values.append((i, val))
                        
                        if len(date_gh_values) >= 5:
                            # 找到符合條件的日期
                            target_date = date
                            # 依index排序，取最新的5個
                            date_gh_values.sort(key=lambda x: x[0], reverse=True)
                            gh_values = [v for _, v in date_gh_values[:5]]
                            break
                
                # 如果沒找到符合條件的日期，返回None表示錯誤
                if not gh_values:
                    return None
                
                # 反轉順序，讓0'對應最後一個值
                gh_values = gh_values[::-1]
                return gh_values
            def convert_clonidine_lab_text(text):
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                gh_values = parse_clonidine_gh_five(lines)
                
                # 檢查是否找到符合條件的資料
                if gh_values is None:
                    return None, None
                
                # 取得日期
                date_match = re.search(r"(2025[0-9]{4})", " ".join(lines))
                date_str = date_match.group(1) if date_match else "20250708"
                date_fmt = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
                target_date = date_str
                time_labels = ["0'", "30'", "60'", "90'", "120'"]
                output = io.StringIO()
                print(f"＝ Clonidine test on {date_fmt} ＝\n", file=output)
                print(format_with_fixed_width(["", "GH"]), file=output)
                header_row = ["時間", "ng/mL"]
                print(format_with_fixed_width(header_row), file=output)
                separator = get_dynamic_separator(header_row)
                print(separator, file=output)
                table_rows = []
                for i, label in enumerate(time_labels):
                    row = [label, gh_values[i] if i < len(gh_values) else "--"]
                    print(format_with_fixed_width(row), file=output)
                    table_rows.append(row)
                print(separator, file=output)
                df = pd.DataFrame.from_records(table_rows, columns=["時間", "GH"])
                return output.getvalue(), df
            result, df = convert_clonidine_lab_text(input_text)
            
            # 檢查是否找到符合條件的資料
            if result is None:
                st.warning("⚠️ 無法擷取任何數值，可能檢驗格式有錯，或是沒有做過此項檢查。")
            else:
                # 判斷主表格是否完全沒有數值
                df_check = df.replace('--', '').replace('', float('nan')).drop('時間', axis=1)
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
                    # 建立正確的日期-時間對應表，最後一行也要補進來
                    dt_pairs = []
                    for i in range(len(date_lines)-1):
                        date = date_lines[i].split('\t')[-1]
                        time = date_lines[i+1].split('\t')[0]
                        dt_pairs.append((date, time))
                    # 補最後一組（最後一行開頭一定有數字）
                    last_line_first_col = date_lines[-1].split('\t')[0]
                    last_line_last_col = date_lines[-1].split('\t')[-1]
                    dt_pairs.append((last_line_last_col, last_line_first_col))
                    num_timepoints = len(dt_pairs)
                    raw_values = parts[4:4+num_timepoints]
                    # 補齊或截斷
                    values = [clean_val(v.strip()) if v.strip() else "--" for v in raw_values]
                    if len(values) < num_timepoints:
                        values += ["--"] * (num_timepoints - len(values))
                    elif len(values) > num_timepoints:
                        values = values[:num_timepoints]
                    for idx, v in enumerate(values):
                        dt = ''
                        if idx < len(dt_pairs):
                            dt = dt_pairs[idx][0]  # 只抓日期
                        if dt != target_date:
                            continue
                        value_to_store = v
                        if code == "72-482":
                            lh_list.append((idx, value_to_store))
                        elif code == "72-483":
                            fsh_list.append((idx, value_to_store))
                        elif code == "72-491":
                            test_list.append((idx, value_to_store))
                        elif code == "72-484":
                            e2_list.append((idx, value_to_store))
                        print(f"idx={idx}, dt={dt}, v={v}")
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
                test_vals = [test_map.get(i, "--") for i in common_idx] if test_list else []
                e2_vals = [e2_map.get(i, "--") for i in common_idx] if e2_list else []
                result = {
                    "LH": lh_vals,
                    "FSH": fsh_vals,
                }
                if test_vals and (test_vals[0] != "--" or (len(test_vals) > 4 and test_vals[4] != "--")):
                    result["Testosterone"] = test_vals
                if e2_vals and (e2_vals[0] != "--" or (len(e2_vals) > 4 and e2_vals[4] != "--")):
                    result["E2"] = e2_vals
                used_codes = ["72-482", "72-483", "72-491", "72-484"]
                #print("DEBUG dt_pairs:", dt_pairs)
                #print("DEBUG target_date:", target_date)
                return result, common_idx, used_codes
            def convert_gnrh_lab_text(text):
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                # 取得日期
                date_match = re.search(r"(2025[0-9]{4})", " ".join(lines))
                date_str = date_match.group(1) if date_match else "20250708"
                date_fmt = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
                target_date = date_str
                result, indices, used_codes = parse_gnrh_lh_fsh_five(lines, target_date)
                # 讓 time_labels 長度與資料列數一致
                num_rows = len(next(iter(result.values())))
                time_labels = [f"{i*30}'" for i in range(num_rows)]
                output = io.StringIO()
                col_names = list(result.keys())
                unit_map = {"LH": "mIU/mL", "FSH": "mIU/mL", "Testosterone": "ng/mL", "E2": "pg/mL"}
                print(f"＝ GnRH stimulation test on {date_fmt} ＝\n", file=output)
                print(format_with_fixed_width([""] + col_names), file=output)
                header_row = ["時間"] + [unit_map.get(n, "") for n in col_names]
                print(format_with_fixed_width(header_row), file=output)
                separator = get_dynamic_separator(header_row)
                print(separator, file=output)
                table_rows = []
                for i, label in enumerate(time_labels):
                    row = [label]
                    for n in col_names:
                        row.append(result.get(n, ["--"]*num_rows)[i])
                    print(format_with_fixed_width(row), file=output)
                    table_rows.append(row)
                print(separator, file=output)
                # debug
                #print("DEBUG result:", result)
                #print("DEBUG num_rows:", num_rows)
                #print("DEBUG time_labels:", time_labels)
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
                df = pd.DataFrame.from_records(table_rows, columns=["時間"] + col_names)
                return output.getvalue(), df, lh_peak, fsh_peak, ratio
            result, df, lh_peak, fsh_peak, ratio = convert_gnrh_lab_text(input_text)
            # 判斷主表格是否完全沒有數值
            df_check = df.replace('--', '').replace('', float('nan')).drop('時間', axis=1)
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
                # 補最後一組
                last_line_first_col = date_lines[-1].split('\t')[0]
                last_line_last_col = date_lines[-1].split('\t')[-1]
                dt_pairs.append((last_line_last_col, last_line_first_col))
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
                print(format_glucagon_width(["", "C-peptide", "Blood Sugar"]), file=output)
                header_row = ["時間", "ng/mL", "mg/dL"]
                print(format_glucagon_width(header_row), file=output)
                separator = get_glucagon_separator(header_row)
                print(separator, file=output)
                table_rows = []
                for i, label in enumerate(time_labels):
                    cpep = cpep_vals[i] if i < len(cpep_vals) else "--"
                    sugar = sugar_vals[i] if i < len(sugar_vals) else "--"
                    row = [label, cpep, sugar]
                    print(format_glucagon_width(row), file=output)
                    table_rows.append(row)
                print(separator, file=output)
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
                df = pd.DataFrame.from_records(table_rows, columns=["時間", "C-peptide", "Blood Sugar"])
                appendix = '''\
\n********************************************************************   
2022年第一型糖尿病申請全民健保重大傷病依據   
C-peptide/glucagon test(residual insulin function)(NTUH)   
   
Age(y)            ＞18y/o      ＜18y/o   
＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝  
Fasting C-P       ＜ 0.5       ＜ 0.5     ng/mL   
6min C-P          ＜ 1.8       ＜ 3.3     ng/mL   
ΔC-P              ＜ 0.7           X      ng/mL   
＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝   
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
            df_check = df.replace('--', '').replace('', float('nan')).drop('時間', axis=1)
            all_empty = df_check.isna().values.all()
            if all_empty:
                st.warning("⚠️ 無法擷取任何數值，可能檢驗格式有錯，或是沒有做過此項檢查。")
            else:
                st.text_area("病歷：", result, height=200)
                st.dataframe(df, use_container_width=True)
                st.download_button("下載文字檔", result, file_name="glucagon_report.txt")
        else:
            st.warning("請先貼上原始data！")