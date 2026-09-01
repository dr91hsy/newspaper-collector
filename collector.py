import os
import re
import json
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import feedparser
from bs4 import BeautifulSoup
import requests

RSS_FEEDS = {
    "조선일보": "https://www.chosun.com/arc/outboundfeeds/rss/category/opinion/?outputType=xml",
    "중앙일보": "https://rss.joongang.co.kr/son/joongang_opinion.xml",
    "동아일보": "https://rss.donga.com/opinion.xml",
    "한겨레": "https://www.hani.co.kr/rss/opinion/",
    "경향신문": "https://www.khan.co.kr/rss/rssdata/opinion_news.xml",
    "오마이뉴스": "http://rss.ohmynews.com/rss/opinion.xml",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_full_content(url, press):
    if not url:
        return ""
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.encoding = res.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(res.text, "html.parser")

        for noise in soup(["script", "style", "aside", "nav", "footer", "iframe", "header", "form", "button"]):
            noise.extract()

        article_body = None
        if press == "조선일보":
            article_body = soup.find("section", class_=re.compile(r"article-body|article-content")) or soup.select_one(".article-body")
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

def is_essay_only(title):
    # 사설 및 딱딱한 정교 정치/사회 논설 키워드 필터링 (제외 대상)
    exclude_keywords = [
        "사설", "[사설]", "社說", "태평로", "만물상", "팔면봉", "분수대", 
        "오늘과 내일", "유레카", "여적", "횡설수설", "시론", "포럼", "특별기고", "시평"
    ]
    if any(kw in title for kw in exclude_keywords):
        return False
    
    # 사설/정치논설이 아닌 에세이, 삶, 문화, 인문, 자유 기고만 남김
    return True

def fetch_and_save():
    today = datetime.now().strftime("%Y-%m-%d")
    output_dir = "opinions"
    os.makedirs(output_dir, exist_ok=True)
    
    daily_file = os.path.join(output_dir, f"{today}.json")
    latest_file = "data.json"

    articles = []

    for press, url in RSS_FEEDS.items():
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            feed = feedparser.parse(response.content)

            press_count = 0
            for entry in feed.entries:
                if press_count >= 2: # 언론사당 에세이/문화 칼럼 최대 2개만 선별
                    break

                title = entry.get("title", "제목 없음").strip()

                # 사설/정치논설 제외하고 에세이류만 수집
                if not is_essay_only(title):
                    continue

                link = entry.get("link", "").strip()
                pub_date = entry.get("published", entry.get("updated", today))
                full_content = fetch_full_content(link, press)

                if not full_content or len(full_content) < 50:
                    if "summary" in entry:
                        full_content = BeautifulSoup(entry.summary, "html.parser").get_text().strip()

                articles.append({
                    "id": f"{press}_{abs(hash(title))}",
                    "press": press,
                    "title": title,
                    "category": "에세이/삶",
                    "pub_date": pub_date,
                    "link": link,
                    "content": full_content or "본문 내용을 가져올 수 없습니다."
                })
                press_count += 1
        except Exception as e:
            print(f"[{press}] RSS 오류: {e}")

    db_payload = {
        "date": today,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_count": len(articles),
        "articles": articles
    }

    with open(daily_file, "w", encoding="utf-8") as f:
        json.dump(db_payload, f, ensure_ascii=False, indent=2)

    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(db_payload, f, ensure_ascii=False, indent=2)

    print(f"JSON DB 저장 완료: {daily_file} (에세이/삶 칼럼 총 {len(articles)}건)")

def send_email():
    mail_user = os.getenv("MAIL_USER")
    mail_pass = os.getenv("MAIL_PASS")
    to_mail = os.getenv("TO_MAIL")
    page_url = os.getenv("PWA_URL", "#")

    if not mail_user or not mail_pass or not to_mail:
        return

    msg = MIMEMultipart("alternative")
    msg['From'] = mail_user
    msg['To'] = to_mail
    msg['Subject'] = f"[에세이 리포트] {datetime.now().strftime('%Y-%m-%d')} 아침 생각거리 모음"

    html_body = f"""
    <div style="font-family: sans-serif; padding: 20px; max-width: 500px; border: 1px solid #e2e8f0; border-radius: 12px;">
      <h2 style="color: #0f172a;">☕ 오늘 자 에세이·생각거리 모음</h2>
      <p style="color: #475569; line-height: 1.5;">사설과 정치 논설을 제외한 주요 언론사의 에세이/문화 칼럼 수집이 완료되었습니다.<br>아래 버튼을 눌러 모바일 카드 뷰어로 편안하게 읽어보세요.</p>
      <a href="{page_url}" style="display: inline-block; background: #2563eb; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; margin-top: 10px;">웹 뷰어로 읽기</a>
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
