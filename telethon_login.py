#!/usr/bin/env python3
"""
telethon_login.py — One-time Telethon session setup.
Run once to create the .session file. Safe to re-run if session is lost.
"""

import os, sys, logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

import config

if not config.TELETHON_API_ID or not config.TELETHON_API_HASH:
    logger.error("TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env")
    sys.exit(1)

if len(sys.argv) < 2:
    print("Usage: python telethon_login.py +6581234567 [<otp>] [<2fa_password>]")
    sys.exit(1)

PHONE   = sys.argv[1].strip()
OTP     = sys.argv[2].strip() if len(sys.argv) > 2 else None
PASSWORD = sys.argv[3].strip() if len(sys.argv) > 3 else None


async def main():
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError

    base = os.path.dirname(os.path.abspath(__file__))
    session_file = os.path.join(base, f"{config.TELETHON_SESSION_NAME}.session")

    client = TelegramClient(session_file, config.TELETHON_API_ID, config.TELETHON_API_HASH)
    await client.connect()

    if not await client.is_connected():
        logger.error("Connection failed.")
        sys.exit(1)

    if await client.is_user_authorized():
        me = await client.get_me()
        logger.info("Already authorised as: %s. No new login needed.", me.first_name)
        await client.disconnect()
        return

    if not OTP:
        await client.send_code_request(PHONE)
        logger.info("OTP code sent to %s. Run again with the code as 2nd argument.", PHONE)
        sys.exit(0)

    try:
        await client.sign_in(PHONE, OTP)
    except SessionPasswordNeededError:
        if not PASSWORD:
            logger.error("2FA password required. Run again with it as 3rd argument.")
            sys.exit(1)
        await client.sign_in(password=PASSWORD)

    me = await client.get_me()
    logger.info("Login successful. Session saved to: %s", session_file)
    logger.info("Authorised as: %s", me.first_name)
    await client.disconnect()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())