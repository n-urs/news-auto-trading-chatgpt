import os
import re
import time
import logging
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playsound import playsound  # for audible error alerts
import openai

# ===== USER CONFIG =====
# We trade only ADA, in two directions: long and short
TOKENS = ["ADA"]
TOKEN_QUANTITIES = {
    ("ADA", "long"):  "10",
    ("ADA", "short"): "20",  # updated short quantity to 20
}
# TELEGRAM CHANNELS ID's to listen. You can create your own channel and add it to run tests
CHANNELS = [-1002442330266, -1002833482708, -1002062626558]

# ===== LOGGING & ENV =====
load_dotenv("config.env")  # In config.env you must define TG_API_ID, TG_API_HASH, TG_PHONE, OPENAI_API_KEY
TG_API_ID        = int(os.getenv("TG_API_ID"))
TG_API_HASH      = os.getenv("TG_API_HASH")
TG_PHONE         = os.getenv("TG_PHONE")
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("telethon").setLevel(logging.WARNING)

# ===== OPENAI CONFIG =====
openai.api_key = OPENAI_API_KEY

# ===== MESSAGE FILTER =====
# Look for substring "Xi" (case-insensitive) in messages from channels that were added for listening
MSG_PATTERN = re.compile(r"xi", flags=re.IGNORECASE)

# ===== TELEGRAM CLIENT =====
client = TelegramClient("ada_xi_bot", TG_API_ID, TG_API_HASH)
token_contexts = {}  # dictionary mapping ("ADA", side) → (context, page)

def play_error_sound():
    try:
        playsound("error.mp3")
    except:
        pass

# --- DISMISS MEXC REMINDERS ------------
async def dismiss_reminders(page):
    """
    Click “No more reminders for today” if present, then close the modal.
    """
    try:
        elm = page.locator('text="No more reminders for today"').first
        await elm.wait_for(timeout=3000)
        await elm.click(force=True)
        logger.info("Clicked ‘No more reminders for today’")
        await asyncio.sleep(0.3)
    except PlaywrightTimeoutError:
        return
    except Exception as e:
        logger.debug(f"No reminder checkbox: {e}")
        return

    try:
        btn = page.locator('button[aria-label="Close"], .ant-modal-close').first
        await btn.wait_for(timeout=2000)
        await btn.click(force=True)
        logger.info("Clicked modal close X")
    except:
        pass

# --- BACKGROUND POPUP BLOCKER ------------
async def popup_blocker(page):
    """
    Continuously check every second for 20 seconds to dismiss any reminder pop-ups.
    """
    deadline = time.time() + 20
    while time.time() < deadline:
        await dismiss_reminders(page)
        await asyncio.sleep(1)

# --- TELEGRAM LOGIN ------------
async def async_telegram_login():
    logger.info("Connecting to Telegram...")
    await client.connect()
    if not await client.is_user_authorized():
        await client.send_code_request(TG_PHONE)
        code = input("Enter Telegram code: ").strip()
        try:
            await client.sign_in(TG_PHONE, code)
        except SessionPasswordNeededError:
            pwd = input("Two-step password: ").strip()
            await client.sign_in(password=pwd)
        logger.info("Telegram login successful.")
    else:
        logger.info("Already logged in.")

# --- OPENAI CALL FOR ANALYSIS ------------
def call_openai_for_analysis(message_text: str) -> str:
    """
    Sends message_text + a tight prompt to the OpenAI API (v1.0+),
    asking for EXACTLY one word ("positive" or "negative") or an empty string.
    Returns the first token of the response (or "" if none).
    """
    prompt = (
        f"Message: \"{message_text}\"\n\n"
        "Analyze whether this message reports results of the phone call with Xi Jinping.  \n"
        "- If you detect that it describes call outcomes, return exactly ONE WORD: “positive” or “negative.”  \n"
        "- Use “positive” if there is no tariff increase, or an overall friendly/constructive tone.  \n"
        "- Use “negative” if there is a tariff increase or aggression.  \n"
        "- If you do NOT see any concrete call-results (or it’s purely speculative), return an empty string (nothing).  \n"
        "- **Send one one-word answer only if there are clear results of the phone call in the message. Do not send the answer if the message simply states that the phone call has ended.**  \n\n"
        "IMPORTANT: Return exactly one token, either “positive” or “negative,” with NO extra text, no punctuation, no newlines.  "
        "If there are no call results, return \"\" (empty).  "
        "Keep in mind previously announced news:  \n"
        "1) US EXTENDS TARIFF PAUSE ON SOME CHINESE GOODS TO AUGUST 31  \n"
        "2) TRUMP NOT CURRENTLY CONSIDERING RE-IMPOSING 145 percent CHINA TARIFFS: CNN  \n"
        "3) President Trump says China has \"violated\" its tariff agreement with the US.  \n"
        "4) US TO CUT TARIFFS ON CHINESE GOODS TO 30 percent FROM 145 percent FOR 90 DAYS: BBG  \n"
        "5) CHINA TO LOWER TARIFFS ON US GOODS TO 10 percent FROM 125 percent FOR 90 DAYS: BBG  \n"
    )

    # Using the new v1.0+ interface:
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an assistant for evaluating negotiation results."},
            {"role": "user",   "content": prompt}
        ],
        temperature=0.0,   # deterministic
        max_tokens=1       # force single token out (“positive” or “negative”), or nothing
        # do not set stream=True
    )

    raw_text = response.choices[0].message.content.strip()
    # In case the model still returns multiple words (rare if max_tokens=1, but just in case),
    # we take only the first word and force it to lowercase.
    first_word = raw_text.split()[0].lower() if raw_text else ""
    if first_word not in ("positive", "negative"):
        return ""
    return first_word

# --- MESSAGE HANDLER ------------
@client.on(events.NewMessage(chats=CHANNELS))
async def handle_new_message(event):
    text = event.message.message or ""
    if not MSG_PATTERN.search(text):
        return

    logger.info(f"Received message containing 'Xi': {text!r}")

    loop = asyncio.get_event_loop()
    try:
        analysis_result = await loop.run_in_executor(None, call_openai_for_analysis, text)
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        play_error_sound()
        return

    # analysis_result is either "positive", "negative", or "".
    if analysis_result == "positive":
        side = "long"
    elif analysis_result == "negative":
        side = "short"
    else:
        # No concrete call-results or neutral → do nothing
        return

    ctx_page = token_contexts.get(("ADA", side))
    if not ctx_page:
        logger.error(f"No page context for ADA-{side}")
        return
    _, page = ctx_page

    action = "Open Long" if side == "long" else "Open Short"
    logger.info(f"Clicking {action} for ADA based on analysis ({analysis_result})")
    try:
        await page.click(f"text={action}")
    except Exception as e:
        logger.error(f"Failed to click {action}: {e}")
        play_error_sound()

# --- RUN BOT ------------
async def run_telegram_bot():
    while True:
        try:
            if not client.is_connected():
                await client.connect()
            await client.run_until_disconnected()
        except (asyncio.CancelledError, KeyboardInterrupt):
            break
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            play_error_sound()
            await asyncio.sleep(5)

# --- SETUP PAGE & LAUNCH BLOCKER ------------
async def setup_page(context, token, side):
    page = await context.new_page()
    page.on("dialog", lambda dlg: asyncio.create_task(dlg.dismiss()))

    # Navigate to contract page and fill in quantity
    await page.goto(f"https://www.mexc.com/futures/{token}_USDT", wait_until="domcontentloaded")
    await asyncio.sleep(1)
    qty = TOKEN_QUANTITIES[(token, side)]
    if qty:
        await page.fill("#mexc_contract_v_open_position input.ant-input", qty)

    # Launch popup blocker in the background
    asyncio.create_task(popup_blocker(page))

    return page

# --- MAIN ENTRY POINT ------------
async def main():
    await async_telegram_login()

    async with async_playwright() as pw:
        # 1) Manual login to capture cookies
        head = await pw.chromium.launch(headless=False)
        ctx0 = await head.new_context()
        p0 = await ctx0.new_page()
        p0.set_default_navigation_timeout(0)
        await p0.goto(f"https://www.mexc.com/futures/{TOKENS[0]}_USDT", wait_until="domcontentloaded")
        input("Log in to MEXC manually, then press ENTER…")
        cookies = await ctx0.cookies()
        await head.close()

        # 2) Open one tab for ADA long and one for ADA short
        browser = await pw.chromium.launch(headless=False)
        for side in ("long", "short"):
            ctx = await browser.new_context(viewport={"width": 960, "height": 540})
            await ctx.add_cookies(cookies)
            page = await setup_page(ctx, "ADA", side)
            token_contexts[("ADA", side)] = (ctx, page)

        # 3) Start listening to Telegram and executing trades
        await run_telegram_bot()

        # 4) Cleanup on exit
        for ctx, page in token_contexts.values():
            await page.close()
            await ctx.close()
        await browser.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown via Ctrl+C")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        play_error_sound()
