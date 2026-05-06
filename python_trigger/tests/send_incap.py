import requests

resp = requests.post(
    "http://127.0.0.1:18000/trigger",
    json={"event": "incap", "source": "test_script"}
)
print("状态码:", resp.status_code)
print("返回:", resp.json())
