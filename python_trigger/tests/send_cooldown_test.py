import requests
import time

URL = "http://127.0.0.1:18000/trigger"

print("连发 3 次 bleeding，间隔 0.3 秒，冷却是 1 秒")
print("期望：第 1 次成功，第 2、3 次被拦")
print()

for i in range(3):
    resp = requests.post(URL, json={"event": "bleeding", "source": "cooldown_test"})
    data = resp.json()
    print(f"第 {i+1} 次：success={data['success']}, action={data['action']}, message={data['message']}")
    time.sleep(0.3)

print()
print("等 1.5 秒后再发一次，冷却应该已过...")
time.sleep(1.5)

resp = requests.post(URL, json={"event": "bleeding", "source": "cooldown_test"})
data = resp.json()
print(f"第 4 次：success={data['success']}, action={data['action']}, message={data['message']}")
