from datetime import datetime
from config import Config

def log(message):
    entry = f"{datetime.now()}: {message}"
    print(entry)
    try:
        with open(Config.LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(f"{entry}\n")
    except Exception as e:
        # Logging should never crash the recorder loop.
        print(f"{datetime.now()}: Warning: failed to write log file: {e}")
