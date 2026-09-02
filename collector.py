import os
import re
import json
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import feedparser
from bs4 import BeautifulSoup
import requests

# 전달해주신 RSS URL 최종 반영
PRESS_CONFIG = {
    "중앙신문": {"url": "https://www.jasm.co.kr/rss/S1N10.xml", "group": "종합", "quota": 2},
    "동아일보": {"url": "https://rss.donga.com/editorials.xml", "group": "보수", "quota": 2},
    "연합뉴스": {"url": "https://www.yna.co.kr/rss/opinion.xml", "group": "뉴스통신", "quota": 2},
    "한겨레온": {"url": "https://www.hanion.co.kr/rss/allArticle.xml", "group": "시민언론", "quota": 2},
    "경향신문": {"url": "https://www.khan.co.kr/rss/rssdata/opinion_news.xml", "group": "진보", "quota": 2},
    "오마이뉴스": {"url": "https://rss.ohmynews.com/rss/ohmynews.xml", "group": "진보", "quota": 2}
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

CONFIG_FILE = "config.json"
HISTORY_FILE = "history.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"themes": {}, "exclude_keywords": ["사설", "[사설]"]}

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def fetch_full_content(url, press):
    if not url:
        return ""
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.encoding = res.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(res.text, "html.parser")

        for noise in soup(["script", "style", "aside", "nav", "footer", "iframe", "header", "form"]):
            noise.extract()

        article_body = None
        if press == "중앙신문":
            article_body = soup.find("article", id="article-view-content-div") or soup.select_one("#article-view-content-div")
        elif press == "동아일보":
            article_body = soup.find("div", class_=re.compile(r"article_txt|news_view")) or soup.select_one(".article_txt")
        elif press == "연합뉴스":
            article_body = soup.find("article", class_=re.compile(r"story-news|article")) or soup.select_one(".story-news")
        elif press == "한겨레온":
            article_body = soup.find("article", id="article-view-content-div") or soup.select_one("#article-view-content-div")
        elif press == "경향신문":
            article_body = soup.find("div", class_=re.compile(r"art_body|articleBody")) or soup.select_one("#articleBody")
        elif press == "오마이뉴스":
            article_body = soup.find("div", class_=re.compile(r"at_contents|mini_at_contents")) or soup.select_one(".at_contents")

        if not article_body:
            article_body = soup.find("article") or soup.find("main")

        if article_body:
            text = article_body.get_text(separator="\n")
        else:
            text = ""

        lines = [line.strip() for line in text.splitlines() if line.strip() and len(line.strip()) > 5]
        return "\n\n".join(lines)
    except Exception as e:
        print(f"[{press}] 원문 수집 실패: {e}")
        return ""

def fetch_and_save():
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    weekday = str(now.weekday())

    config = load_config()
    themes = config.get("themes", {})
    exclude_keywords = config.get("exclude_keywords", [])
    
    theme_info = themes.get(weekday, {"theme": "오늘의 에세이", "desc": "아침 에세이 큐레이션"})

    output_dir = "opinions"
    os.makedirs(output_dir, exist_ok=True)
    
    daily_file = os.path.join(output_dir, f"{today_str}.json")
    latest_file = "data.json"

    history = load_history()
    cutoff_date = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    history = {link: date for link, date in history.items() if date >= cutoff_date}

    selected_articles = []

    for press, info in PRESS_CONFIG.items():
        try:
            response = requests.get(info["url"], headers=HEADERS, timeout=10)
            feed = feedparser.parse(response.content)

            collected_count = 0
            for entry in feed.entries:
                if collected_count >= info["quota"]:
                    break

                title = entry.get("title", "").strip()
                if any(kw in title for kw in exclude_keywords):
                    continue

                link = entry.get("link", "").strip()
                if not link or link in history:
                    continue

                content = fetch_full_content(link, press)
                if not content or len(content) < 80:
                    continue

                selected_articles.append({
                    "id": f"{press}_{abs(hash(title))}",
                    "press": press,
                    "group": info["group"],
                    "title": title,
                    "category": theme_info.get("theme", "에세이"),
                    "pub_date": today_str,
                    "link": link,
                    "content": content
                })

                history[link] = today_str
                collected_count += 1
                print(f"[{press}] 수집 성공: {title}")

        except Exception as e:
            print(f"[{press}] 수집 오류: {e}")

    save_history(history)

    db_payload = {
        "date": today_str,
        "theme": theme_info.get("theme", "오늘의 에세이"),
        "theme_desc": theme_info.get("desc", ""),
        "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "total_count": len(selected_articles),
        "articles": selected_articles
    }

    with open(daily_file, "w", encoding="utf-8") as f:
        json.dump(db_payload, f, ensure_ascii=False, indent=2)

    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(db_payload, f, ensure_ascii=False, indent=2)

    print(f"총 {len(selected_articles)}개 기사 수집 및 저장 완료.")

def send_email():
    mail_user = os.getenv("MAIL_USER")
    mail_pass = os.getenv("MAIL_PASS")
    to_mail = os.getenv("TO_MAIL")
    page_url = os.getenv("PWA_URL", "#")

    if not mail_user or not mail_pass or not to_mail:
        return

    now = datetime.now()
    config = load_config()
    theme_name = config.get("themes", {}).get(str(now.weekday()), {}).get("theme", "오늘의 에세이")

    intent_url = page_url
    if page_url.startswith("https://"):
        raw_domain = page_url.replace("https://", "")
        intent_url = f"intent://{raw_domain}#Intent;scheme=https;package=com.android.chrome;end"

    msg = MIMEMultipart("alternative")
    msg['From'] = mail_user
    msg['To'] = to_mail
    msg['Subject'] = f"[{theme_name}] {now.strftime('%Y-%m-%d')} 아침 에세이"

    html_body = f"""
    <div style="font-family: sans-serif; padding: 20px; max-width: 500px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
      <h2 style="color: #0f172a; margin-top:0;">☕ 오늘 자 에세이 큐레이션</h2>
      <p style="color: #2563eb; font-weight: bold; margin-bottom: 5px;">오늘의 테마: {theme_name}</p>
      <p style="color: #475569; font-size: 14px; line-height: 1.5;">그룹웨어 갇힘 방지를 위해 아래 <b>[Chrome으로 열기]</b>를 클릭하시거나 주소를 복사해 브라우저에 붙여넣어 주세요.</p>
      
      <div style="margin: 20px 0;">
        <a href="{intent_url}" style="display: block; text-align: center; background: #2563eb; color: #ffffff; padding: 14px 0; text-decoration: none; border-radius: 10px; font-weight: bold; font-size: 15px;">🚀 Chrome 앱으로 직접 열기</a>
      </div>

      <div style="background-color: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0; font-size: 12px; color: #64748b; word-break: break-all;">
        <b>웹 주소 복사용:</b><br>{page_url}
      </div>
    </div>
    """
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(mail_user, mail_pass)
        server.send_message(msg)
        server.close()
    except Exception as e:
        print(f"메일 발송 오류: {e}")

if __name__ == "__main__":
    fetch_and_save()
    send_email()
