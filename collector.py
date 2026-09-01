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

        # 불필요한 태그 미리 제거
        for noise in soup(["script", "style", "aside", "nav", "footer", "iframe", "header", "form", "button"]):
            noise.extract()

        article_body = None

        # 언론사별 정밀 본문 태그 타겟팅
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

        # 예외 처리: 지정 태그가 없을 경우 공통 컨테이너 탐색
        if not article_body:
            article_body = soup.find("article") or soup.find("main")

        if article_body:
            # 본문 내부 기고자 소개, 이미지 설명 등 노이즈 제거
            for extra in article_body.find_all(["figure", "figcaption", "table", "div"]):
                if extra.get("class") and any(c in str(extra.get("class")) for c in ["byline", "reporter", "img", "photo", "copyright"]):
                    extra.extract()
            
            # 본문 텍스트 획득 (줄바꿈 보존)
            text = article_body.get_text(separator="\n")
        else:
            text = ""

        # 빈 줄 정돈 및 가독성 다듬기
        lines = [line.strip() for line in text.splitlines() if line.strip() and len(line.strip()) > 5]
        return "\n\n".join(lines)
    except Exception as e:
        print(f"[{press}] 원문 수집 실패: {e}")
        return ""

def classify_entry(title):
    title_lower = title.lower()
    if "사설" in title_lower or "[사설]" in title or "社說" in title:
        return "사설"
    staff_keywords = ["태평로", "만물상", "팔면봉", "분수대", "시시각각", "오늘과 내일", "아침햇살", "유레카", "여적", "경향시론", "횡설수설", "기자수첩", "데스크 칼럼"]
    if any(kw in title for kw in staff_keywords):
        return "자사 칼럼"
    guest_keywords = ["시론", "포럼", "아침을 열며", "시사칼럼", "광장", "특별기고", "시평", "공감"]
    if any(kw in title for kw in guest_keywords):
        return "외부 기고/시론"
    return "기타/에세이"

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

            for entry in feed.entries[:10]: # 최근 10개 우선 수집
                title = entry.get("title", "제목 없음").strip()
                link = entry.get("link", "").strip()
                pub_date = entry.get("published", entry.get("updated", today))

                full_content = fetch_full_content(link, press)
                
                # 원문 추출이 실패한 경우에만 RSS 요약본으로 대체
                if not full_content or len(full_content) < 50:
                    if "summary" in entry:
                        full_content = BeautifulSoup(entry.summary, "html.parser").get_text().strip()

                category = classify_entry(title)

                articles.append({
                    "id": f"{press}_{abs(hash(title))}",
                    "press": press,
                    "title": title,
                    "category": category,
                    "pub_date": pub_date,
                    "link": link,
                    "content": full_content or "본문 내용을 가져올 수 없습니다."
                })
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

    print(f"JSON DB 저장 완료: {daily_file} (총 {len(articles)}건)")

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
    msg['Subject'] = f"[칼럼 모음] {datetime.now().strftime('%Y-%m-%d')} 일간 리포트"

    html_body = f"""
    <div style="font-family: sans-serif; padding: 20px; max-width: 500px; border: 1px solid #e2e8f0; border-radius: 12px;">
      <h2 style="color: #0f172a;">📰 오늘 자 오피니언 칼럼 모음</h2>
      <p style="color: #475569; line-height: 1.5;">오늘 자 주요 언론사 오피니언 전문 수집이 완료되었습니다.<br>아래 버튼을 눌러 모바일/데스크톱 카드 뷰어 앱으로 바로 이동하세요.</p>
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
