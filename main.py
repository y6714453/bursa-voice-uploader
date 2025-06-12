import json
import yfinance as yf
import asyncio
import datetime
import os
import subprocess
from edge_tts import Communicate
from requests_toolbelt.multipart.encoder import MultipartEncoder
import requests
import urllib.request
import tarfile

USERNAME = "0733181201"
PASSWORD = "6714453"
TOKEN = f"{USERNAME}:{PASSWORD}"
ASSETS_FILE = "assets.json"
FFMPEG_PATH = "./bin/ffmpeg"

# הורדת ffmpeg אם לא קיים
def ensure_ffmpeg():
    if not os.path.exists(FFMPEG_PATH):
        print("⬇️ מוריד ffmpeg...")
        os.makedirs("bin", exist_ok=True)
        url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
        archive_path = "bin/ffmpeg.tar.xz"
        extract_path = "bin"
        urllib.request.urlretrieve(url, archive_path)
        with tarfile.open(archive_path) as tar:
            tar.extractall(path=extract_path)
        for root, dirs, files in os.walk(extract_path):
            for file in files:
                if file == "ffmpeg":
                    os.rename(os.path.join(root, file), FFMPEG_PATH)
                    os.chmod(FFMPEG_PATH, 0o755)
                    break

# יצירת טקסט לפי סוג הנכס
def create_text(asset, data):
    name = asset["name"]
    type_ = asset["type"]
    currency = "שְׁקָלִים" if type_ == "stock_il" else "דּוֹלָר"
    unit = "נְקוּדוֹת" if type_ in ["index", "sector"] else currency

    if type_ == "index":
        intro = f"מָדָד {name} עוֹמֵד כָּעֵת עַל {data['current']} {unit}."
    elif type_ == "sector":
        intro = f"סֶקְטוֹר {name} עוֹמֵד כָּעֵת עַל {data['current']} {unit}."
    elif type_ == "stock_il":
        intro = f"מַנְיָת {name} נִסְחֶרֶת כָּעֵת בְּשַׁעַר שֶׁל {data['current']} {unit}."
    elif type_ == "stock_us":
        intro = f"מַנְיָת {name} נִסְחֶרֶת כָּעֵת בְּשַׁעַר שֶׁל {data['current']} {unit}."
    elif type_ == "crypto":
        intro = f"מַטְבֵּעַ {name} נִסְחָר כָּעֵת בְּשַׁעַר שֶׁל {data['current']} דּוֹלָר."
    elif type_ == "forex":
        intro = f"{name} אֶחָד שָׁוֶה {data['current']} שֶׁקֶל."
    elif type_ == "commodity":
        intro = f"{name} נִסְחָר כָּעֵת בְּשַׁעַר שֶׁל {data['current']} דּוֹלָר."
    else:
        intro = f"{name} נִסְחָר כָּעֵת בְּ{data['current']}"

    return (
        f"{intro} "
        f"מִתְּחִלַּת הַיּוֹם נִרְשְׁמָה {data['change_day']}. "
        f"מִתְּחִלַּת הַשָּׁבוּעַ נִרְשְׁמָה {data['change_week']}. "
        f"בִּשְׁלוֹשֶׁת הַחֳדָשִׁים הָאַחֲרוֹנִים נִרְשְׁמָה {data['change_3m']}. "
        f"מִתְּחִלַּת הַשָּׁנָה נִרְשְׁמָה {data['change_year']}. "
        f"הַמְּחִיר הַנּוֹכְחִי רָחוֹק מֵהַשִּׂיא בְּ{data['from_high']} אָחוּז."
    )

async def text_to_speech(text, filename):
    communicate = Communicate(text, voice="he-IL-AvriNeural")
    await communicate.save(filename)

def convert_to_wav(mp3_file, wav_file):
    ensure_ffmpeg()
    subprocess.run([FFMPEG_PATH, "-y", "-i", mp3_file, "-ar", "8000", "-ac", "1", "-acodec", "pcm_s16le", wav_file])

def upload_to_yemot(wav_file, path):
    m = MultipartEncoder(fields={
        'token': TOKEN,
        'path': path + "001.wav",
        'file': ("001.wav", open(wav_file, 'rb'), 'audio/wav')
    })
    requests.post("https://www.call2all.co.il/ym/api/UploadFile", data=m, headers={'Content-Type': m.content_type})

def get_stock_data(symbol):
    t = yf.Ticker(symbol)
    hist = t.history(period="1y")
    if hist.empty:
        return None

    today = hist.iloc[-1]["Close"]
    week = hist.iloc[-5]["Close"] if len(hist) >= 5 else today
    quarter = hist.iloc[-60]["Close"] if len(hist) >= 60 else today
    year = hist.iloc[0]["Close"]
    high = hist["Close"].max()

    def format_change(from_, to):
        percent = round((to - from_) / from_ * 100, 2)
        direction = "עֲלִיָּה" if percent > 0 else "יְרִידָה" if percent < 0 else "שְׁמִירָה עַל יַצִּיבוּת"
        return f"{direction} שֶׁל {abs(percent)} אָחוּז"

    from_high = round((high - today) / high * 100, 2)
    return {
        "current": round(today, 2),
        "change_day": format_change(hist.iloc[-2]["Close"], today),
        "change_week": format_change(week, today),
        "change_3m": format_change(quarter, today),
        "change_year": format_change(year, today),
        "from_high": from_high
    }

async def main_loop():
    print("🔁 לולאה התחילה...")
    while True:
        with open(ASSETS_FILE, "r", encoding="utf-8") as f:
            assets = json.load(f)

        for asset in assets:
            symbol = asset["symbol"]
            name = asset["name"]
            path = asset["target_path"]

            print(f"📈 {name} ({symbol})...")
            data = get_stock_data(symbol)
            if data is None:
                print(f"⚠️ אין נתונים עבור {symbol}")
                continue

            text = create_text(asset, data)
            await text_to_speech(text, "temp.mp3")
            convert_to_wav("temp.mp3", "temp.wav")
            upload_to_yemot("temp.wav", path)
            print(f"✅ הועלה לשלוחה {path}")

        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main_loop())
