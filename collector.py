import os
import re
import json
from datetime import datetime
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import feedparser
from bs4 import BeautifulSoup
import requests

RSS_FEEDS = {
    # 보수 디비전
    "조선일보": {"url": "https://www.chosun.com/arc/outboundfeeds/rss/category/opinion/?outputType=xml", "group": "보수"},
    "중앙일보": {"url": "https://rss.joongang.co.kr/son/joongang_opinion.xml", "group": "보수"},
    "동아일보": {"url": "https://rss.donga.com/opinion.xml", "group": "보수"},
    # 진보 디비전
    "한겨레": {"url": "https://www.hani.co.kr/rss/opinion/", "group": "진보"},
    "경향신문": {"url": "https://www.khan.co.kr/rss/rssdata/opinion_news.xml", "group": "진보"},
    "오마이뉴스": {"url": "http://rss.ohmynews.com/rss/opinion.xml", "group": "진보"},
    # 방송 디비전
    "YTN": {"url": "https://m.ytn.co.kr/rss/opinion.xml", "group": "방송"}
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

THEMES = {
    0: {"name": "삶 & 성찰", "desc": "일상, 관계, 삶의 태도, 휴식에 관한 생각"},
    1: {"name": "문화 & 예술", "desc": "책, 영화, 미술, 음악, 공간, 여행 이야기"},
    2: {"name": "인문 & 철학", "desc": "역사와 철학, 세상을 바라보는 지적 시선"},
    3: {"name": "사회 & 트렌드", "desc": "세대, 라이프스타일, 기술과 인간성"},
    4: {"name": "주말의 길목 (자유)", "desc": "위트 있는 수필과 가벼운 신변잡기"},
    5: {"name": "주말의 휴식", "desc": "주말에 읽는 가벼운 에세이"},
    6: {"name": "주말의 휴식", "desc": "주말에 읽는 가벼운 에세이"}
}

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
        if press == "조선일보":
            article_body = (
                soup.find("section", class_=re.compile(r"article-body|article-content")) or
                soup.find("div", class_=re.compile(r"article-body|article-content|article_body")) or
                soup.find(attrs={"itemprop": "articleBody"}) or
                soup.select_one(".article-body")
            )
        elif press == "중앙일보":
            article_body = soup.find("div", class_=re.compile(r"article_body|article_content")) or soup.select_one("#article_body")
        elif press == "동아일보":
            article_body = soup.find("div", class_=re.compile(r"article_txt|news_view")) or soup.select_one(".article_txt")
        elif press == "한겨레":
            article_body = soup.find("div", class_=re.compile(r"text|article-text")) or soup.select_one(".text")
        elif press == "경향신문":
            article_body = soup.find("div", class_=re.compile(r"art_body|articleBody")) or soup.select_one("#articleBody")
        elif press == "오마이뉴스":
            article_body = soup.find("div", class_=re.compile(r"at_contents|mini_at_contents")) or soup.select_one(".at_contents")
        elif press == "YTN":
            article_body = soup.find("div", class_=re.compile(r"zone-article|article_text|paragraph")) or soup.select_one("#zone-article")

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

def is_essay_candidate(title):
    exclude_keywords = [
        "사설", "[사설]", "社說", "태평로", "만물상", "팔면봉", "분수대", 
        "오늘과 내일", "유레카", "여적", "횡설수설", "기자수첩", "데스크 칼럼",
        "대통령", "국회", "여당", "야당", "검찰", "정치", "당정", "선거"
    ]
    return not any(kw in title for kw in exclude_keywords)

def fetch_and_save():
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    weekday = now.weekday()
    theme_info = THEMES.get(weekday, THEMES[0])

    output_dir = "opinions"
    os.makedirs(output_dir, exist_ok=True)
    
    daily_file = os.path.join(output_dir, f"{today_str}.json")
    latest_file = "data.json"

    candidates = {"보수": [], "진보": [], "방송": []}

    for press, info in RSS_FEEDS.items():
        group = info["group"]
        try:
            response = requests.get(info["url"], headers=HEADERS, timeout=10)
            feed = feedparser.parse(response.content)

            for entry in feed.entries:
                title = entry.get("title", "제목 없음").strip()
                if not is_essay_candidate(title):
                    continue

                link = entry.get("link", "").strip()
                pub_date = entry.get("published", entry.get("updated", today_str))
                
                candidates[group].append({
                    "press": press,
                    "title": title,
                    "link": link,
                    "pub_date": pub_date
                })
        except Exception as e:
            print(f"[{press}] RSS 수집 오류: {e}")

    selected_articles = []

    # 보수 3개, 진보 3개, 방송 2개 추출 (부족 시 다른 기사로 무작위 보충)
    def pick_articles(group_key, count):
        items = candidates[group_key]
        random.shuffle(items)
        picked = items[:count]
        for item in picked:
            content = fetch_full_content(item["link"], item["press"])
            selected_articles.append({
                "id": f"{item['press']}_{abs(hash(item['title']))}",
                "press": item["press"],
                "group": group_key,
                "title": item["title"],
                "category": theme_info["name"],
                "pub_date": item["pub_date"],
                "link": item["link"],
                "content": content or "본문 내용을 가져올 수 없습니다."
            })

    pick_articles("보수", 3)
    pick_articles("진보", 3)
    pick_articles("방송", 2)

    db_payload = {
        "date": today_str,
        "theme": theme_info["name"],
        "theme_desc": theme_info["desc"],
        "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "total_count": len(selected_articles),
        "articles": selected_articles
    }

    with open(daily_file, "w", encoding="utf-8") as f:
        json.dump(db_payload, f, ensure_ascii=False, indent=2)

    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(db_payload, f, ensure_ascii=False, indent=2)

    print(f"JSON DB 저장 완료: {daily_file} (오늘의 테마: {theme_info['name']} / 총 {len(selected_articles)}편)")

def send_email():
    mail_user = os.getenv("MAIL_USER")
    mail_pass = os.getenv("MAIL_PASS")
    to_mail = os.getenv("TO_MAIL")
    page_url = os.getenv("PWA_URL", "#")

    if not mail_user or not mail_pass or not to_mail:
        return

    now = datetime.now()
    theme_name = THEMES.get(now.weekday(), THEMES[0])["name"]

    msg = MIMEMultipart("alternative")
    msg['From'] = mail_user
    msg['To'] = to_mail
    msg['Subject'] = f"[{theme_name}] {now.strftime('%Y-%m-%d')} 아침 에세이 8선"

    html_body = f"""
    <div style="font-family: sans-serif; padding: 20px; max-width: 500px; border: 1px solid #e2e8f0; border-radius: 12px;">
      <h2 style="color: #0f172a;">☕ 오늘 자 에세이 큐레이션</h2>
      <p style="color: #2563eb; font-weight: bold;">오늘의 테마: {theme_name}</p>
      <p style="color: #475569; line-height: 1.5;">보수 3편, 진보 3편, YTN 2편 총 8편의 정제된 에세이가 준비되었습니다.<br>아래 버튼을 눌러 모바일 앱으로 읽어보세요.</p>
      <a href="{page_url}" style="display: inline-block; background: #2563eb; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; margin-top: 10px;">앱에서 읽기</a>
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
