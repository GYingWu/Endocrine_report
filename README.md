# Endocrine Report Tool

This is a Streamlit-based tool for formatting Insulin/TRH/GnRH test reports. It automatically converts raw laboratory data into standardized tables and clinical note formats, making it convenient for clinical use and data organization.

## Features
- Paste raw laboratory data and automatically generate clinical note format
- Download the report as a text file
- Display a complete table of all test items and all time points

## Try Online
You can use this tool directly via Streamlit Cloud:

👉 [Cloud App Link](https://endocrinereport-3ytuvxsdtixzeextjbpczq.streamlit.app/)

## Local Installation & Usage

1. Clone this repository:
   ```bash
   git clone https://github.com/GYingWu/Endocrine_report.git
   cd Endocrine_report
   ```
2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```
3. Launch the Streamlit app:
   ```bash
   streamlit run Endocrine_report.py
   ```

## Example requirements.txt
```
streamlit
pandas
```

## How to Deploy on Streamlit Cloud
1. Push this project to your GitHub repository.
2. Go to [https://streamlit.io/cloud](https://streamlit.io/cloud) and log in.
3. Click "New app", select your repo and `Endocrine_report.py`.
4. Click "Deploy".

---

For questions or suggestions, please open an issue on [GitHub Issues](https://github.com/GYingWu/Endocrine_report/issues)! 