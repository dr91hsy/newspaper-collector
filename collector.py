import os
import re
import json
from datetime import datetime, timedelta
import feedparser
from bs4 import BeautifulSoup
import requests
from pywebpush import webpush, WebPushException

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

    # 스크립트 실행 위치 기준 절대 경로 설정
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(BASE_DIR, "opinions")
    os.makedirs(output_dir, exist_ok=True)
    
    daily_file = os.path.join(output_dir, f"{today_str}.json")
    latest_file = os.path.join(BASE_DIR, "data.json")

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
    return db_payload

def send_push_notification(payload):
    """수집이 끝나면 등록된 기기로 Web Push 알림을 보낸다.
    필요한 값(VAPID_PRIVATE_KEY, VAPID_SUBJECT, PUSH_SUBSCRIPTION)이 아직 없으면
    (=폰에서 아직 알림 구독을 안 했으면) 조용히 건너뛴다."""
    vapid_private_key = os.getenv("VAPID_PRIVATE_KEY")
    vapid_subject = os.getenv("VAPID_SUBJECT")
    subscription_raw = os.getenv("PUSH_SUBSCRIPTION")
    page_url = os.getenv("PWA_URL", "https://dr91hsy.github.io/newspaper-collector/")

    if not vapid_private_key or not vapid_subject or not subscription_raw:
        print("푸시 알림 설정이 아직 없어 발송을 건너뜁니다 (VAPID_PRIVATE_KEY/VAPID_SUBJECT/PUSH_SUBSCRIPTION).")
        return

    if not payload or not payload.get("total_count"):
        print("새로 수집된 기사가 없어 알림을 보내지 않습니다.")
        return

    try:
        subscription_info = json.loads(subscription_raw)
    except json.JSONDecodeError as e:
        print(f"PUSH_SUBSCRIPTION 파싱 실패: {e}")
        return

    theme_name = payload.get("theme", "오늘의 에세이")
    total_count = payload.get("total_count", 0)

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({
                "title": f"[{theme_name}] 오늘의 에세이 도착",
                "body": f"{total_count}개의 칼럼이 준비됐어요. 눌러서 확인해보세요.",
                "url": page_url,
            }, ensure_ascii=False),
            vapid_private_key=vapid_private_key,
            vapid_claims={"sub": vapid_subject},
        )
        print("푸시 알림 발송 완료.")
    except WebPushException as e:
        print(f"푸시 알림 발송 실패: {e}")

if __name__ == "__main__":
    result = fetch_and_save()
    send_push_notification(result)
