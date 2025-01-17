import requests
from bs4 import BeautifulSoup
import pandas as pd

# Headers เพื่อเลี่ยงการถูกบล็อก
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# ฟังก์ชันสำหรับ Cointelegraph
def fetch_cointelegraph_news():
    url = "https://cointelegraph.com/"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"Failed to fetch Cointelegraph. Status code: {response.status_code}")
        return []

    soup = BeautifulSoup(response.content, "html.parser")
    articles = soup.find_all("a", class_="post-card-inline__title-link")

    news_list = []
    for article in articles:
        title = article.text.strip()
        link = "https://cointelegraph.com" + article['href']
        # ดึงเนื้อหาข่าว
        content = fetch_article_content(link)
        news_list.append({"source": "Cointelegraph", "title": title, "link": link, "content": content})

    return news_list

# ฟังก์ชันสำหรับดึงเนื้อหาข่าวจากลิงก์
def fetch_article_content(link):
    try:
        response = requests.get(link, headers=HEADERS)
        if response.status_code != 200:
            return "Failed to fetch content."

        soup = BeautifulSoup(response.content, "html.parser")
        content_section = soup.find("div", class_="article-content")
        if not content_section:
            content_section = soup.find("div", class_="content")

        if content_section:
            return " ".join(content_section.stripped_strings)
        else:
            return "No content available."
    except Exception as e:
        return f"Error fetching content: {str(e)}"

# รวมข่าวจากหลายแหล่ง
def fetch_all_news():
    all_news = []
    print("Fetching Cointelegraph news...")
    all_news.extend(fetch_cointelegraph_news())

    return all_news

# เรียกฟังก์ชันและบันทึกข้อมูล
news = fetch_all_news()
if news:
    df = pd.DataFrame(news)
    df.to_csv("crypto_news.csv", index=False)
    print("News saved to 'crypto_news.csv'")
else:
    print("No news found.")
