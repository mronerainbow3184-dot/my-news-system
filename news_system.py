import os
import time
import feedparser
import requests
import urllib.parse
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai

# --- 設定（環境変数から取得） ---
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = "3316352339af8056a2e5f0939ba88e7d"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GMAIL_ADDRESS = "mr.onerainbow3184@gmail.com"
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

# Gemini初期化
client_gemini = genai.Client(api_key=GEMINI_API_KEY)
TARGET_MODEL = "gemini-2.5-flash" 

def get_notion_data():
    """NotionからActiveなキーワードを取得"""
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    # ActiveチェックボックスがONのものだけ抽出
    payload = {"filter": {"property": "Active", "checkbox": {"equals": True}}}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        
        if "object" in data and data["object"] == "error":
            print(f"!! Notion API Error: {data.get('message')}")
            return []

        configs = []
        for page in data.get("results", []):
            p = page.get("properties", {})
            # プロパティ名の取得（柔軟に対応）
            name_prop = p.get("Name") or p.get("名前")
            name = name_prop["title"][0]["plain_text"] if name_prop and name_prop["title"] else "ニュース"
            
            period_prop = p.get("Period") or p.get("期間")
            period = period_prop.get("select", {}).get("name", "1d") if period_prop and period_prop.get("select") else "1d"
            
            configs.append({"name": name, "period": period})
        return configs
    except Exception as e:
        print(f" ! Notion Connection Error: {e}")
        return []

def send_html_email(summaries):
    """HTML形式でメールを送信"""
    now_str = datetime.now().strftime("%Y/%m/%d")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"【朝のニュース要約】{now_str}"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = GMAIL_ADDRESS

    html_body = f"""
    <html>
    <body style="font-family: sans-serif; color: #333; line-height: 1.6;">
        <h2 style="color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 8px;">☀️ 本日のニュース要約</h2>
    """
    for item in summaries:
        html_body += f"""
        <div style="margin-bottom: 30px; padding: 15px; background-color: #f8f9fa; border-radius: 8px; border-left: 5px solid #1a73e8;">
            <h3 style="margin-top: 0; color: #202124;">📌 {item['name']} ({item['period']})</h3>
            <p style="white-space: pre-wrap;">{item['summary']}</p>
            <div style="margin-top: 15px;">
                <a href="{item['url']}" style="background-color: #1a73e8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">Googleニュースで確認</a>
            </div>
        </div>
        """
    html_body += "<p style='font-size: 12px; color: #777;'>※GitHub Actionsより自動配信</p></body></html>"
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print(" ✓ メール送信完了")
    except Exception as e:
        print(f" ! Mail Error: {e}")

def run_news_flow():
    print(f"--- NewsFetcher: {datetime.now().strftime('%Y-%m-%d %H:%M')} ---")
    configs = get_notion_data()
    if not configs:
        print("!! 配信対象のキーワードがありません。")
        return

    all_summaries = []
    for i, conf in enumerate(configs):
        if i > 0: time.sleep(2) # APIレート制限対策
        
        print(f">> 処理中: {conf['name']}")
        query = urllib.parse.quote(conf["name"])
        rss_url = f"https://news.google.com/rss/search?q={query}+when:{conf['period']}&hl=ja&gl=JP&ceid=JP:ja"
        display_url = rss_url.replace("/rss/search", "/search")
        
        feed = feedparser.parse(rss_url)
        if not feed.entries:
            continue
            
        titles = "\n".join([f"- {e.title}" for e in feed.entries[:5]])
        prompt = f"「{conf['name']}」に関する最新ニュースを、要点を3点に絞って簡潔にまとめてください。\n\n{titles}"
        
        try:
            response = client_gemini.models.generate_content(model=TARGET_MODEL, contents=prompt)
            all_summaries.append({
                "name": conf["name"], "period": conf["period"], "summary": response.text, "url": display_url
            })
        except Exception as e:
            print(f" ! Gemini Error ({conf['name']}): {e}")

    if all_summaries:
        send_html_email(all_summaries)
    print("--- 全ての処理が完了しました ---")

if __name__ == "__main__":
    run_news_flow()