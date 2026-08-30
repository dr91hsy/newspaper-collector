import os
import re
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import feedparser
from bs4 import BeautifulSoup
import requests # requests 모듈 활용

# RSS 피드 주소 목록
RSS_FEEDS = {
    "조선일보": "https://www.chosun.com/arc/outboundfeeds/rss/category/opinion/?outputType=xml",
    "중앙일보": "https://rss.joongang.co.kr/son/joongang_opinion.xml",
    "동아일보": "https://rss.donga.com/opinion.xml",
    "한겨레": "https://www.hani.co.kr/rss/opinion/",
    "경향신문": "https://www.khan.co.kr/rss/rssdata/opinion_news.xml",
    "오마이뉴스": "http://rss.ohmynews.com/rss/opinion.xml",
}

def clean_html(raw_html):
    """HTML 태그 제거 및 텍스트 정화"""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator="\n")
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

def classify_entry(title, summary=""):
    """제목 및 본문 키워드 기반 4대 카테고리 자동 분류"""
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

    # 브라우저 차단 회피용 User-Agent 헤더
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print("오피니언 데이터 수집 및 분류 중...")

    for press, url in RSS_FEEDS.items():
        try:
            # requests로 헤더를 실어서 안전하게 RSS 데이터 가져오기 (타임아웃 10초 설정)
            response = requests.get(url, headers=headers, timeout=10)
            feed = feedparser.parse(response.content)

            if not feed.entries:
                print(f"[{press}] 수집된 기사 없음 또는 서버 응답 비어있음.")
                continue

            for entry in feed.entries:
                title = entry.get("title", "제목 없음")
                link = entry.get("link", "")
                pub_date = entry.get("published", entry.get("updated", "날짜 정보 없음"))

                content = ""
                if "content" in entry:
                    content = entry.content[0].value
                elif "summary" in entry:
                    content = entry.summary
                elif "description" in entry:
                    content = entry.description

                clean_content = clean_html(content)
                category = classify_entry(title, clean_content)

                classified_data[category].append({
                    "press": press,
                    "title": title,
                    "pub_date": pub_date,
                    "link": link,
                    "content": clean_content
                })

        except Exception as e:
            # 특정 언론사 서버 오류가 나더라도 스크립트가 죽지 않고 넘어가도록 예외 처리
            print(f"[{press}] 수집 실패 (네트워크/서버 오류): {e}")
            continue

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("==================================================\n")
        f.write(f"   조중동 & 한경오 분류별 오피니언 모음 ({today})\n")
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

    print(f"수집 완료: {filepath}")
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
