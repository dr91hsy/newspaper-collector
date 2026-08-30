# 📰 Newspaper Opinion Aggregator & Classifier

> **Automated daily intelligence pipeline for Korea's top tier press.**

An automated end-to-end RSS intelligence pipeline built with Python and GitHub Actions. This project scrapes, cleans, categorizes, and archives daily op-eds, editorials, and expert columns from South Korea’s leading major daily newspapers (**Chosun, JoongAng, Donga, Hani, Kyunghyang, and Ohmynews**), delivering structured `.txt` digests straight to your inbox every morning.

---

## ⚡ Key Features

* **⚡ Automated Execution**: Fully serverless pipeline powered by **GitHub Actions** (runs daily at 07:00 KST / 22:00 UTC).
* **🎯 Smart Classification**: Automatically categorizes fetched articles into 4 distinct structural buckets using keyword-matching logic:
  1. **Editorials (`사설`)**
  2. **Staff Columns (`자사 칼럼`)**
  3. **Guest & External Opinions (`외부 기고/시론`)**
  4. **Essays & Culture (`기타/문화·에세이`)**
* **📬 Email Delivery**: Sends the newly compiled `.txt` digest as a direct attachment via **Gmail SMTP**.
* **📱 Cross-Platform Accessibility**: Access and edit raw daily archives on any device via GitHub Web/Mobile or read directly in your native email viewer.

---

## 🏗️ Architecture Flow
[6 Major Press RSS Feeds]
│
▼
┌─────────────────────────┐
│ GitHub Actions Runner   │
│ (Daily @ 07:00 KST)     │
└────────┬────────────────┘
│
▼
┌─────────────────────────┐
│ Python Processor        │
│ ├── HTML Cleaning       │
│ └── Smart Categorization│
└────────┬────────────────┘
│
├───▶ Save & Commit to Repository (/opinions/opinions_YYYY-MM-DD.txt)
│
└───▶ Dispatch Email via Gmail SMTP (.txt Attached)

---

## 🛠️ Tech Stack & Dependencies

* **Language**: `Python 3.11`
* **Workflow Automation**: `GitHub Actions`
* **Parsing & Scraping**: `feedparser`, `beautifulsoup4`
* **Delivery Protocol**: `smtplib` (SSL encrypted)

---

## 📁 Repository Structure
.
├── .github/
│   └── workflows/
│       └── daily_collector.yml    # GitHub Actions workflow schedule & config
├── opinions/                      # Automated archive folder for daily .txt files
├── collector.py                   # Core processing & classifier script
├── requirements.txt               # Dependencies list
└── README.md                      # Documentation

---

## 🔐 Environment Variables Configuration

To run the automated email dispatcher, configure the following **Repository Secrets** under `Settings > Secrets and variables > Actions`:

| Variable Name | Description |
| :--- | :--- |
| `MAIL_USER` | Sending Gmail address |
| `MAIL_PASS` | 16-digit Google App Password |
| `TO_MAIL` | Destination recipient email address |

---

<p align="center">
  <i>Automating media insight consumption, one morning at a time.</i>
</p>
