import time
import feedparser
import subprocess
import requests
import urllib.parse
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai

# --- 1. 設定（あなたの情報を入力） ---
NOTION_TOKEN = "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"
DATABASE_ID = "3316352339af8056a2e5f0939ba88e7d"
GEMINI_API_KEY = "AIzaSyDyB28WOqNqqtudDXWJwUPXas4lwhdzj7g"

# Gmail通知設定
GMAIL_ADDRESS = "mr.onerainbow3184@gmail.com"
GMAIL_APP_PASSWORD = "vdsmoeslrjoxwfdr" 

# Gemini初期化 (1.5でも2.0でも機能せず2.5で実装)
client_gemini = genai.Client(api_key=GEMINI_API_KEY)
TARGET_MODEL = "gemini-2.5-flash" 

def get_notion_data():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    payload = {"filter": {"property": "Active", "checkbox": {"equals": True}}}
    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        configs = []
        for page in data.get("results", []):
            p = page.get("properties", {})
            name = p["Name"]["title"][0]["plain_text"] if p.get("Name") and p["Name"]["title"] else "ニュース"
            configs.append({"name": name, "url": p.get("ReferenceURL", {}).get("url")})
        return configs
    except: return []

def send_html_email(summaries):
    """HTMLメールを作成して送信する"""
    now_str = datetime.now().strftime("%Y/%m/%d")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"【朝のニュース要約】{now_str}"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = GMAIL_ADDRESS

    # HTML本文の組み立て
    html_body = f"""
    <html>
    <body style="font-family: sans-serif; color: #333; line-height: 1.6;">
        <h2 style="color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 8px;">☀️ 本日のニュース要約</h2>
    """
    
    for item in summaries:
        html_body += f"""
        <div style="margin-bottom: 30px; padding: 15px; background-color: #f8f9fa; border-radius: 8px;">
            <h3 style="margin-top: 0; color: #202124;">📌 {item['name']}</h3>
            <p style="white-space: pre-wrap;">{item['summary']}</p>
            <div style="margin-top: 15px;">
                <a href="{item['url']}" style="background-color: #1a73e8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">元記事をチェック</a>
            </div>
        </div>
        """
    
    html_body += """
        <p style="font-size: 12px; color: #777;">※このメールはNewsFetcher Systemより自動送信されています。</p>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print("   ✓ HTMLメールを送信しました。")
    except Exception as e:
        print(f"   ! メール送信エラー: {e}")

def run_news_flow():
    print(f"\n[{datetime.now().strftime('%H:%M')}] 巡回及び通知処理を開始...")
    configs = get_notion_data()
    if not configs: return

    all_summaries = [] # メール用のデータを貯めるリスト
    combined_voice_text = "" # 音声読み上げ用の一括テキスト

    for i, conf in enumerate(configs):
        if i > 0: time.sleep(10) # API負荷軽減
        
        print(f">> 取得中: {conf['name']}")
        query = urllib.parse.quote(conf["name"])
        rss_url = conf["url"] if conf["url"] else f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
        display_url = rss_url.replace("/rss/search", "/search")
        feed = feedparser.parse(rss_url)
        
        if not feed.entries: continue
            
        titles = "\n".join([f"- {e.title}" for e in feed.entries[:5]])
        prompt = f"「{conf['name']}」のニュース。読み上げ用に短く3分以内で傾向を把握できる要約。記号不要。\n\n{titles}"
        
        try:
            response = client_gemini.models.generate_content(model=TARGET_MODEL, contents=prompt)
            summary = response.text
            print(f"【要約】\n{summary}")
            
            # リストに追加
            all_summaries.append({
                "name": conf["name"],
                "summary": summary,
                "url": display_url
            })
            combined_voice_text += f"\n次は、{conf['name']}についてです。{summary}"

        except Exception as e:
            print(f"   ! Geminiエラー: {e}")

    # 1. 音声合成と再生（全件分）
    if combined_voice_text:
        from gtts import gTTS
        gTTS(text=combined_voice_text, lang='ja').save("news.mp3")
        subprocess.run(['start', 'news.mp3'], shell=True)
        print("   ✓ 音声再生を開始しました。")

    # 2. メール送信（全件まとめて1通）
    if all_summaries:
        send_html_email(all_summaries)

if __name__ == "__main__":
    print("--- NewsFetcher System [Production Mode] ---")
    run_news_flow()
    print("\n[待機中] プログラムを終了するには Ctrl+C を押してください。")
    while True:
        try: time.sleep(60)
        except KeyboardInterrupt: break