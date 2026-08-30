===============================================================================
                  NEWSPAPER OPINION AGGREGATOR & CLASSIFIER
===============================================================================

Automated daily intelligence pipeline for Korea's top tier press.

An automated end-to-end RSS intelligence pipeline built with Python and GitHub 
Actions. This project scrapes, cleans, categorizes, and archives daily op-eds, 
editorials, and expert columns from South Korea's leading major daily newspapers 
(Chosun, JoongAng, Donga, Hani, Kyunghyang, and Ohmynews), delivering structured 
.txt digests straight to your inbox every morning.


-------------------------------------------------------------------------------
1. KEY FEATURES
-------------------------------------------------------------------------------

* Automated Execution:
  Fully serverless pipeline powered by GitHub Actions (runs daily at 07:00 KST).

* Smart Classification:
  Automatically categorizes fetched articles into 4 distinct structural buckets:
    1. Editorials (사설)
    2. Staff Columns (자사 칼럼)
    3. Guest & External Opinions (외부 기고/시론)
    4. Essays & Culture (기타/문화·에세이)

* Email Delivery:
  Sends the newly compiled .txt digest as a direct attachment via Gmail SMTP.

* Cross-Platform Accessibility:
  Access raw daily archives on any device via GitHub Web/Mobile or read 
  directly in your native email viewer.


-------------------------------------------------------------------------------
2. ARCHITECTURE FLOW
-------------------------------------------------------------------------------

  [6 Major Press RSS Feeds]
             |
             v
  [GitHub Actions Runner (Daily @ 07:00 KST)]
             |
             v
  [Python Processor]
             |
             +---> HTML Cleaning & Parsing
             +---> Smart Keyword Categorization
             |
             v
  [Save & Commit to Repository]
    -> /opinions/opinions_YYYY-MM-DD.txt
             |
             v
  [Dispatch Email via Gmail SMTP]
    -> (.txt File Attached)


-------------------------------------------------------------------------------
3. TECH STACK & DEPENDENCIES
-------------------------------------------------------------------------------

* Language: Python 3.11
* Workflow Automation: GitHub Actions
* Parsing & Scraping: feedparser, beautifulsoup4
* Delivery Protocol: smtplib (SSL encrypted)


-------------------------------------------------------------------------------
4. REPOSITORY STRUCTURE
-------------------------------------------------------------------------------

.
├── .github/
│   └── workflows/
│       └── daily_collector.yml    # Workflow schedule & config
├── opinions/                      # Archive folder for daily .txt files
├── collector.py                   # Core processing & classifier script
├── requirements.txt               # Dependencies list
└── README.md                      # Documentation


-------------------------------------------------------------------------------
5. ENVIRONMENT VARIABLES CONFIGURATION
-------------------------------------------------------------------------------

To run the automated email dispatcher, configure the following Repository Secrets 
under Settings > Secrets and variables > Actions:

  * MAIL_USER : Sending Gmail address
  * MAIL_PASS : 16-digit Google App Password
  * TO_MAIL   : Destination recipient email address


===============================================================================
          Automating media insight consumption, one morning at a time.
===============================================================================
