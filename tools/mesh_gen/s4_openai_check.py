#!/usr/bin/env python3
"""S4 候選17 前置檢查(免費,不產圖不計費):確認 OPENAI_API_KEY 已設定、能連到 api.openai.com、
key 有效、帳號能看到 gpt-image-2。只讀環境變數;絕不印出 key(只印末 4 碼)。
用法: python3 tools/mesh_gen/s4_openai_check.py
"""
import json, os, sys, urllib.request, urllib.error

MODEL = "gpt-image-2"


def main():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("FAIL 1/3 OPENAI_API_KEY 未設定(環境變數不存在)。設定方式見 knowledge/s4-gptfill-api-key-setup.md")
        return 2
    print(f"OK   1/3 OPENAI_API_KEY 已設定(結尾 …{key[-4:]},長度 {len(key)})")
    req = urllib.request.Request(f"https://api.openai.com/v1/models/{MODEL}",
                                 headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
        print("OK   2/3 可連線且 key 有效")
        print(f"OK   3/3 帳號可存取模型 {d.get('id')}")
        return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        hint = {401: "key 無效/已撤銷", 403: "key 無權限或組織未通過驗證(gpt-image 系列常需 Organization Verification)",
                404: f"帳號看不到 {MODEL}(未開通或需組織驗證)", 429: "額度/速率限制(檢查 billing 餘額)"}.get(e.code, "")
        print(f"FAIL 2-3/3 HTTP {e.code} {hint}" + ("" if e.code == 401 else f"\n     {body}"))
        return 3
    except Exception as e:  # 網路層(沙盒/代理擋 api.openai.com 屬此類)
        print(f"FAIL 2/3 連線失敗:{type(e).__name__}: {e}\n     若在雲端排程環境,檢查 Environment 的網路存取是否允許 api.openai.com")
        return 4


if __name__ == "__main__":
    sys.exit(main())
