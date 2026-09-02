import os
import re
import json
from datetime import datetime, timedelta
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import feedparser
from bs4 import BeautifulSoup
import requests

PRESS_CONFIG = {
    # 보수 디비전 (목표 총 2~3편)
    "중앙일보": {"url": "https://rss.joongang.co.kr/son/joongang_opinion.xml", "group": "보수", "quota": 2},
    "동아일보": {"url": "https://rss.donga.com/opinion.xml", "group": "보수", "quota": 2},
    
    # 진보 디비전 (목표 총 2~3편)
    "경향신문": {"url": "https://www.khan.co.kr/rss/rssdata/opinion_news.xml", "group": "진보", "quota": 2},
    "오마이뉴스": {"url": "http://rss.ohmynews.com/rss/opinion.xml", "group": "진보", "quota": 2}
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
    return {
        "themes": {
            "0": {"theme": "삶 & 성찰", "desc": "일상, 관계, 삶의 태도"},
            "1": {"theme": "문화 & 예술", "desc": "책, 영화, 미술, 음악"},
            "2": {"theme": "인문 & 철학", "desc": "역사와 철학, 세상을 보는 시선"},
            "3": {"theme": "사회 & 트렌드", "desc": "세대, 라이프스타일, 기술"},
            "4": {"theme": "주말의 길목", "desc": "가벼운 수필과 신변잡기"}
        },
        "exclude_keywords": ["사설", "[사설]", "분수대", "오늘과 내일", "횡설수설", "여적", "기자수첩", "정치", "대통령", "국회"]
    }

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
        session = requests.Session()
        res = session.get(url, headers=HEADERS, timeout=10)
        res.encoding = res.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(res.text, "html.parser")

        for noise in soup(["script", "style", "aside", "nav", "footer", "iframe", "header", "form", "button"]):
            noise.extract()

        article_body = None
        if press == "중앙일보":
            article_body = soup.find("div", class_=re.compile(r"article_body|article_content")) or soup.select_one("#article_body")
        elif press == "동아일보":
            article_body = soup.find("div", class_=re.compile(r"article_txt|news_view")) or soup.select_one(".article_txt")
        elif press == "경향신문":
            article_body = soup.find("div", class_=re.compile(r"art_body|articleBody")) or soup.select_one("#articleBody")
        elif press == "오마이뉴스":
            article_body = soup.find("div", class_=re.compile(r"at_contents|mini_at_contents")) or soup.select_one(".at_contents")

        if not article_body:
            article_body = soup.find("article") or soup.find("main")

        if article_body:
            for extra in article_body.find_all(["figure", "figcaption", "table", "div"]):
                if extra.get("class") and any(c in str(extra.get("class")) for c in ["byline", "reporter", "img", "photo", "copyright"]):
                    extra.extract()
            text = article_body.get_text(separator="\n")
        else:
            text = ""

        lines = [line.strip() for line in text.splitlines() if line.strip() and len(line.strip()) > 5]
        return "\n\n".join(lines)
    except Exception as e:
        print(f"[{press}] 원문 수집 실패: {e}")
        return ""

def is_essay_candidate(title, exclude_keywords):
    return not any(kw in title for kw in exclude_keywords)

def fetch_and_save():
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    weekday = str(now.weekday())

    # 주말(토/일)인 경우 수집 패스 가능 구조 (월~금 테마 적용)
    config = load_config()
    themes = config.get("themes", {})
    exclude_keywords = config.get("exclude_keywords", [])
    
    theme_info = themes.get(weekday, {"theme": "주말의 휴식", "desc": "주말에 읽는 가벼운 에세이"})

    output_dir = "opinions"
    os.makedirs(output_dir, exist_ok=True)
    
    daily_file = os.path.join(output_dir, f"{today_str}.json")
    latest_file = "data.json"

    # 언론사별 3일 중복 히스토리 관리
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

                title = entry.get("title", "제목 없음").strip()
                if not is_essay_candidate(title, exclude_keywords):
                    continue

                link = entry.get("link", "").strip()
                if not link or link in history:
                    continue

                content = fetch_full_content(link, press)
                if not content or len(content) < 100:
                    continue

                pub_date = entry.get("published", entry.get("updated", today_str))

                selected_articles.append({
                    "id": f"{press}_{abs(hash(title))}",
                    "press": press,
                    "group": info["group"],
                    "title": title,
                    "category": theme_info.get("theme", "에세이"),
                    "pub_date": pub_date,
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
        "theme": theme_info.get("theme", "오늘의 생각"),
        "theme_desc": theme_info.get("desc", "아침 에세이 큐레이션"),
        "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "total_count": len(selected_articles),
        "articles": selected_articles
    }

    with open(daily_file, "w", encoding="utf-8") as f:
        json.dump(db_payload, f, ensure_ascii=False, indent=2)

    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(db_payload, f, ensure_ascii=False, indent=2)

    print(f"JSON DB 저장 완료: {daily_file} (총 {len(selected_articles)}편)")

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

    # Android Chrome Intent Scheme 링크 생성 (그룹웨어 인앱 브라우저 강제 이탈용)
    intent_url = page_url
    if page_url.startswith("https://"):
        raw_url = page_url.replace("https://", "")
        intent_url = f"intent://{raw_url}#Intent;scheme=https;package=com.android.chrome;end"

    msg = MIMEMultipart("alternative")
    msg['From'] = mail_user
    msg['To'] = to_mail
    msg['Subject'] = f"[{theme_name}] {now.strftime('%Y-%m-%d')} 아침 에세이"

    html_body = f"""
    <div style="font-family: sans-serif; padding: 20px; max-width: 500px; border: 1px solid #e2e8f0; border-radius: 12px;">
      <h2 style="color: #0f172a;">☕ 오늘 자 에세이 큐레이션</h2>
      <p style="color: #2563eb; font-weight: bold;">오늘의 테마: {theme_name}</p>
      <p style="color: #475569; line-height: 1.5;">엄선된 보수/진보 4개 언론사의 에세이가 준비되었습니다.<br>아래 버튼을 눌러 모바일 앱으로 읽어보세요.</p>
      
      <div style="margin-top: 15px;">
        <a href="{page_url}" target="_blank" rel="noopener noreferrer" style="display: inline-block; background: #2563eb; color: #ffffff; padding: 12px 20px; text-decoration: none; border-radius: 8px; font-weight: bold; margin-right: 5px;">웹으로 열기</a>
        <a href="{intent_url}" style="display: inline-block; background: #0f172a; color: #ffffff; padding: 12px 20px; text-decoration: none; border-radius: 8px; font-weight: bold;">Chrome 앱 열기</a>
      </div>
      
      <p style="color: #94a3b8; font-size: 12px; margin-top: 15px;">* 그룹웨어 내부에서 페이지가 안 열릴 경우 'Chrome 앱 열기'를 누르시거나 주소를 복사해 기본 브라우저에 붙여넣어 주세요.</p>
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
