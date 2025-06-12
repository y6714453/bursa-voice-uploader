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
from num2words import num2words

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

# עיבוד מספרים עם "ו" לפי כללים מדויקים
def format_number_hebrew(number):
    try:
        number = float(number)
        if number.is_integer():
            return build_hebrew_number_parts(int(number))
        else:
            whole = int(number)
            decimal_str = str(round(number, 2)).split(".")[1].ljust(2, '0')
            decimal_num = int(decimal_str)
            decimal_word = refine_hebrew_number(num2words(decimal_num, lang='he'))

            if whole == 0:
                return f"אֶפֶס נְקוּדָה {decimal_word}"
            else:
                whole_word = build_hebrew_number_parts(whole)
                return f"{whole_word} נְקוּדָה {decimal_word}"
    except:
        return str(number)

def build_hebrew_number_parts(number):
    parts = []
    thousands = number // 1000
    hundreds = (number % 1000) // 100
    tens_units = number % 100

    if thousands:
        if thousands in [3, 4, 6, 7, 8, 9]:
            word = num2words(thousands, lang='he')
            parts.append(refine_hebrew_number(word + "ת") + " אֲלָפִים")
        elif thousands >= 10:
            word = num2words(thousands, lang='he')
            parts.append(refine_hebrew_number(word) + " אֶלֶף")
        else:
            word = num2words(thousands, lang='he')
            parts.append(refine_hebrew_number(word) + " אֶלֶף")

    if hundreds:
        if thousands >= 10:
            parts.append(refine_hebrew_number(num2words(hundreds * 100, lang='he')))
        else:
            parts.append("וֵ" + refine_hebrew_number(num2words(hundreds * 100, lang='he')))

    if tens_units:
        if hundreds:
            if tens_units >= 10 and tens_units % 10 != 0:
                tens = tens_units - (tens_units % 10)
                units = tens_units % 10
                parts.append(refine_hebrew_number(num2words(tens, lang='he')) + " ו" + refine_hebrew_number(num2words(units, lang='he')))
            else:
                parts.append(refine_hebrew_number(num2words(tens_units, lang='he')))
        else:
            parts.append("וֵ" + refine_hebrew_number(num2words(tens_units, lang='he')))

    return ' '.join(parts)

# שיפור ו' חיבור
def refine_hebrew_number(text):
    text = text.replace(" ו", " וֵ")
    words = text.split()
    for i, word in enumerate(words):
        if word == "אחד" and i > 0 and words[i - 1] == "וֵ":
            words[i] = "אֶחָד"
    return ' '.join(words)

# יצירת טקסט לפי סוג הנכס
def create_text(asset, data):
    name = asset["name"]
    type_ = asset["type"]
    currency = "שְׁקָלִים" if type_ == "stock_il" else "דּוֹלָר"
    unit = "נְקוּדוֹת" if type_ in ["index", "sector"] else currency
    current = format_number_hebrew(data['current'])
    from_high = format_number_hebrew(data['from_high'])

    if type_ == "index":
        intro = f"מָדָד {name} עוֹמֵד כָּעֵת עַל {current} {unit}."
    elif type_ == "sector":
        intro = f"סֶקְטוֹר {name} עוֹמֵד כָּעֵת עַל {current} {unit}."
    elif type_ == "stock_il":
        intro = f"מַנְיָת {name} נִסְחֶרֶת כָּעֵת בְּשַׁעַר שֶׁל {current} {unit}."
    elif type_ == "stock_us":
        intro = f"מַנְיָת {name} נִסְחֶרֶת כָּעֵת בְּשַׁעַר שֶׁל {current} {unit}."
    elif type_ == "crypto":
        intro = f"מַטְבֵּעַ {name} נִסְחָר כָּעֵת בְּשַׁעַר שֶׁל {current} דּוֹלָר."
    elif type_ == "forex":
        intro = f"{name} אֶחָד שָׁוֶה {current} שֶׁקֶל."
    elif type_ == "commodity":
        intro = f"{name} נִסְחָר כָּעֵת בְּשַׁעַר שֶׁל {current} דּוֹלָר."
    else:
        intro = f"{name} נִסְחָר כָּעֵת בְּ{current}"

    pause = " <break time=\"500ms\"/>"
    full_text = (
        f"{intro}{pause}"
        f"{data['change_day']}{pause}"
        f"{data['change_week']}{pause}"
        f"{data['change_3m']}{pause}"
        f"{data['change_year']}{pause}"
        f"הַמְּחִיר הַנּוֹכְחִי רָחוֹק מֵהַשִּׂיא בְּ{from_high} אָחוּז."
    )
    print(f"📜 טקסט עבור {name}: {full_text}")
    return full_text

async def text_to_speech(text, filename):
    communicate = Communicate(text, voice="he-IL-AvriNeural", rate="-10%")
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

    def format_change(from_, to, prefix):
        percent = round((to - from_) / from_ * 100, 2)
        if percent == 0:
            return f"{prefix} לֹא חָל שִׁנּוּי."
        direction = "עֲלִיָּה" if percent > 0 else "יְרִידָה"
        return f"{prefix} נִרְשְׁמָה {direction} שֶׁל {format_number_hebrew(abs(percent))} אָחוּז."

    from_high = round((high - today) / high * 100, 2)
    return {
        "current": today,
        "change_day": format_change(hist.iloc[-2]["Close"], today, "מִתְּחִלַּת הַיּוֹם"),
        "change_week": format_change(week, today, "מִתְּחִלַּת הַשָּׁבוּעַ"),
        "change_3m": format_change(quarter, today, "בִּשְׁלוֹשֶׁת הַחֳדָשִׁים הָאַחֲרוֹנִים"),
        "change_year": format_change(year, today, "מִתְּחִלַּת הַשָּׁנָה"),
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

        await asyncio.sleep(180)

if __name__ == "__main__":
    asyncio.run(main_loop())
