# Endocrine Report Tool

這是一個整理兒童內分泌科相關檢測的工具，需使用新版檢驗報告複製後貼上生成病歷格式。

## 主要功能
- 支援多種內分泌動態測試格式：
  - Insulin/TRH/GnRH test
  - Clonidine test
  - GnRH stimulation test
  - Glucagon test for C-peptide function
- 自動解析原始 LIS 資料，產生主表格、同日檢驗項目表格、完整所有項目表格
- 可下載標準化文字檔，直接複製到病歷系統

## 安裝與使用方式
1. 安裝依賴：
   ```
   pip install -r requirements.txt
   ```
2. 啟動工具：
   ```
   streamlit run Endocrine_report.py
   ```
3. 在網頁介面貼上原始檢驗資料，點擊「產生病歷格式」即可自動產生標準化表格與病歷格式。

## 常見問題與注意事項
- 請確保原始資料格式與 LIS 匯出一致，欄位順序不可任意更動。
- 若遇到特殊欄位或新檢驗項目，請於 OPTIONAL_CODES/OPTIONAL_NAMES 裡補充。
- 若遇到「無法擷取任何數值」警告，請檢查原始資料格式或是否有做過該項檢查。
- 下載的文字檔可直接複製到電子病歷或 Word 編輯。

---
如有問題或建議，歡迎於 GitHub issue 討論！ 