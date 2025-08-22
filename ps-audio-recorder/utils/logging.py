from datetime import datetime
from config import Config

def log(message):
    print(f"{datetime.now()}: {message}")
    with open(Config.LOG_FILE, "a") as log_file:
        log_file.write(f"{datetime.now()}: {message}\n")
