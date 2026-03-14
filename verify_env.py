import os
from dotenv import load_dotenv

load_dotenv()

keys = ["CCTV_API_KEY", "WEATHER_SERVICE_KEY", "KAKAO_APP_KEY"]
for key in keys:
    value = os.environ.get(key)
    print(f"{key}: {'OK' if value else 'MISSING'}")
    if value:
        print(f"  Value length: {len(value)}")

#.env 키 잘 가져오나 테스트용