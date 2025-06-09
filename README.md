This particular example was created for auto-trading the Trump-Xi call that took place on June 5, 2025.

**Automated ADA Crypto-Futures Trading Bot** using Telegram, OpenAI, and Playwright

## Features

1. **Multi-channel Listening**
   * Monitors three Telegram channels (including Trump’s Truth Social via a Telegram bridge).
   * Filters messages containing the substring **"Xi"** (case-insensitive).

2. **AI-driven Sentiment Classification**
   * Sends matching messages to OpenAI’s **gpt-3.5-turbo** (via `chat.completions.create`).
   * Uses a strict prompt to return **exactly one word**: **`positive`** or **`negative`**.
   * Ignores messages without clear call results or only stating that the call ended.

3. **Automated Trade Execution**
   * Opens **long** or **short** ADA futures positions on **MEXC** via **Playwright**.
   * Pre-fills quantity (`long = 10`, `short = 20`) per user config.
   * Handles and dismisses pop-up reminders automatically.

4. **Rapid Reaction**
   * Executes trade within seconds of message arrival.
   * Example: Detected "call went well" in **3 s**, opened long, and netted **\$2 000** profit in **30 s**.

5. **Error Handling & Logging**
   * Plays an audible alert on errors (e.g., API failures or click issues).
   * Detailed logs for Telegram events, OpenAI calls, and browser actions.


## INSTALLATION

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-username/news-auto-trading-chatgpt.git
   cd news-auto-trading-chatgpt
   ```

2. **Create a virtual environment & install dependencies**

   ```bash
   python -m venv venv
   source venv/bin/activate      # Linux/macOS
   venv\Scripts\activate       # Windows
   pip install -r requirements.txt
   ```

3. **Configure environment variables**

   * Duplicate `config.example.env` to `config.env`
   * Fill in your credentials:

     ```ini
     TG_API_ID=<your_telegram_api_id>
     TG_API_HASH=<your_telegram_api_hash>
     TG_PHONE=<your_phone_number>
     OPENAI_API_KEY=<your_openai_api_key>
     ```

4. **Run the bot**

   ```bash
   python bot.py
   ```

## Configuration

| Variable         | Description                                  |
| ---------------- | -------------------------------------------- |
| `TG_API_ID`      | Telegram API ID (from my.telegram.org)       |
| `TG_API_HASH`    | Telegram API hash                            |
| `TG_PHONE`       | Phone number linked to your Telegram account |
| `OPENAI_API_KEY` | API key for OpenAI                           |

## License

This project is licensed under the **MIT License**. See `LICENSE` for details.
