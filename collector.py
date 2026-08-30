import os
import re
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import feedparser
from bs4 import BeautifulSoup
import requests

# RSS 피드 주소 목록
RSS_FEEDS = {
    "조선일보": "https://www.chosun.com/arc/outboundfeeds/rss/category/opinion/?outputType=xml",
    "중앙일보": "https://rss.joongang.co.kr/son/joongang_opinion.xml",
    "동아일보": "https://rss.donga.com/opinion.xml",
    "한겨레": "https://www.hani.co.kr/rss/opinion/",
    "경향신문": "https://www.khan.co.kr/rss/rssdata/opinion_news.xml",
    "오마이뉴스": "http://rss.ohmynews.com/rss/opinion.xml",
}

# 브라우저 접속 위장용 헤더
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_full_content(url, press):
    """기사 URL 접속 후 언론사별 본문 전체 크롤링 및 불필요 요소 제거"""
    if not url:
        return ""
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.encoding = res.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(res.text, "html.parser")

        # 불필요한 태그 제거 (스크립트, 스타일, 주석, 광고 등)
        for element in soup(["script", "style", "aside", "nav", "footer", "iframe", "header"]):
            element.extract()

        article_body = None

        # 언론사별 본문 영역 지정
        if press == "조선일보":
            article_body = soup.find("section", class_=re.compile(r"article-body")) or soup.find("section", id="article-body")
        elif press == "중앙일보":
            article_body = soup.find("div", class_=re.compile(r"article_body")) or soup.find("div", id="article_body")
        elif press == "동아일보":
            article_body = soup.find("div", class_=re.compile(r"article_txt")) or soup.find("section", class_="news_view")
        elif press == "한겨레":
            article_body = soup.find("div", class_="text") or soup.find("div", class_=re.compile(r"article-text"))
        elif press == "경향신문":
            article_body = soup.find("div", class_="art_body") or soup.find("div", id="articleBody")
        elif press == "오마이뉴스":
            article_body = soup.find("div", class_="at_contents") or soup.find("div", class_="mini_at_contents")

        # 공통 예비(fallback) 본문 검색
        if not article_body:
            article_body = soup.find("article") or soup.find("main")

        if article_body:
            # 본문 내 이미지 설명, 기자 정보 등 잡다한 요소 제거
            for noise in article_body.find_all(["figure", "figcaption", "script", "button"]):
                noise.extract()
            text = article_body.get_text(separator="\n")
        else:
            text = soup.get_text(separator="\n")

        # 줄바꿈 정돈 및 정제
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = "\n\n".join(lines)
        return clean_text

    except Exception as e:
        print(f"[{press}] 본문 원문 수집 실패 ({url}): {e}")
        return ""

def classify_entry(title):
    """제목 기반 4대 카테고리 자동 분류"""
    title_lower = title.lower()
    
    # 1. 사설
    if "사설" in title_lower or "[사설]" in title or "社說" in title:
        return "1. 사설 (Editorial)"
    
    # 2. 자사 고정 칼럼
    staff_keywords = [
        "태평로", "만물상", "팔면봉", "분수대", "시시각각", "오늘과 내일", 
        "아침햇살", "유레카", "여적", "경향시론", "횡설수설", "기자수첩", 
        "데스크 칼럼", "논설위원", "선임기자", "대기자"
    ]
    if any(kw in title for kw in staff_keywords):
        return "2. 자사 칼럼 (Staff Column)"
    
    # 3. 외부 필진 기고 및 시론
    guest_keywords = [
        "시론", "포럼", "아침을 열며", "시사칼럼", "광장", "특별기고", 
        "시평", "공감", "교수", "변호사", "연구원"
    ]
    if any(kw in title for kw in guest_keywords):
        return "3. 외부 기고/시론 (Guest Column)"
    
    # 4. 기타/에세이
    return "4. 기타/문화·에세이 (General & Essay)"

def fetch_and_save():
    today = datetime.now().strftime("%Y-%m-%d")
    output_dir = "opinions"
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"opinions_{today}.txt")

    classified_data = {
        "1. 사설 (Editorial)": [],
        "2. 자사 칼럼 (Staff Column)": [],
        "3. 외부 기고/시론 (Guest Column)": [],
        "4. 기타/문화·에세이 (General & Essay)": []
    }

    print("오피니언 RSS 수집 및 본문 크롤링 시작...")

    for press, url in RSS_FEEDS.items():
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            feed = feedparser.parse(response.content)

            if not feed.entries:
                print(f"[{press}] 수집된 기사 목록 없음")
                continue

            for entry in feed.entries:
                title = entry.get("title", "제목 없음").strip()
                link = entry.get("link", "").strip()
                pub_date = entry.get("published", entry.get("updated", "날짜 정보 없음"))

                # 기사 URL에 직접 접속하여 전문 크롤링
                full_content = fetch_full_content(link, press)

                # 크롤링 실패 시 RSS 기본 요약문 가져오기 (fallback)
                if not full_content:
                    if "content" in entry:
                        full_content = entry.content[0].value
                    elif "summary" in entry:
                        full_content = entry.summary
                    elif "description" in entry:
                        full_content = entry.description
                    full_content = BeautifulSoup(full_content, "html.parser").get_text(separator="\n").strip()

                category = classify_entry(title)

                classified_data[category].append({
                    "press": press,
                    "title": title,
                    "pub_date": pub_date,
                    "link": link,
                    "content": full_content
                })
                print(f"  - [{press}] {title[:20]}... (수집 완료)")

        except Exception as e:
            print(f"[{press}] RSS 피드 수집 실패: {e}")
            continue

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("==================================================\n")
        f.write(f"   조중동 & 한경오 분류별 오피니언 전문 모음 ({today})\n")
        f.write("==================================================\n\n")

        for category_name, items in classified_data.items():
            f.write("##################################################\n")
            f.write(f"  {category_name} (총 {len(items)}건)\n")
            f.write("##################################################\n\n")

            if not items:
                f.write("해당 카테고리의 수집된 항목이 없습니다.\n\n")
                continue

            for idx, item in enumerate(items, 1):
                f.write(f"[{idx}] [{item['press']}] {item['title']}\n")
                f.write(f"발행일: {item['pub_date']}\n")
                f.write(f"링크: {item['link']}\n")
                f.write("-" * 40 + "\n")
                f.write(f"{item['content']}\n")
                f.write("\n" + "=" * 40 + "\n\n")

    print(f"전체 수집 완료: {filepath}")
    return filepath, f"opinions_{today}.txt"

def send_email(filepath, filename):
    """Gmail을 이용한 TXT 첨부파일 자동 발송"""
    mail_user = os.getenv("MAIL_USER")
    mail_pass = os.getenv("MAIL_PASS")
    to_mail = os.getenv("TO_MAIL")

    if not mail_user or not mail_pass or not to_mail:
        print("이메일 환경변수가 설정되지 않아 발송을 건너뜁니다.")
        return

    msg = MIMEMultipart()
    msg['From'] = mail_user
    msg['To'] = to_mail
    msg['Subject'] = f"[칼럼 모음] {filename}"

    msg.attach(MIMEText("오늘 자 주요언론사 카테고리별 칼럼 모음입니다.", 'plain', 'utf-8'))

    with open(filepath, 'rb') as f:
        part = MIMEApplication(f.read(), Name=filename)
        part['Content-Disposition'] = f'attachment; filename="{filename}"'
        msg.attach(part)

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(mail_user, mail_pass)
        server.send_message(msg)
        server.close()
        print("이메일 발송 성공!")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")

if __name__ == "__main__":
    filepath, filename = fetch_and_save()
    send_email(filepath, filename)
