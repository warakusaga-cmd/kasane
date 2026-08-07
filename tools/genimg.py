import os,sys,json,base64,urllib.request

KEY=os.environ["GEMINI_API_KEY"]
MODEL=os.environ.get("IMG_MODEL","gemini-3-pro-image")
prompt=sys.argv[1]; out=sys.argv[2]
url=f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={KEY}"
body={"contents":[{"parts":[{"text":prompt}]}],
      "generationConfig":{"responseModalities":["IMAGE"]}}
req=urllib.request.Request(url,data=json.dumps(body).encode(),
    headers={"Content-Type":"application/json"})
try:
    r=json.load(urllib.request.urlopen(req,timeout=180))
except urllib.error.HTTPError as e:
    print("HTTP",e.code,e.read().decode()[:400]); sys.exit(1)
parts=r.get("candidates",[{}])[0].get("content",{}).get("parts",[])
for p in parts:
    d=p.get("inlineData") or p.get("inline_data")
    if d:
        open(out,"wb").write(base64.b64decode(d["data"]))
        print("OK",out,os.path.getsize(out),"bytes"); sys.exit(0)
print("NO IMAGE:",json.dumps(r)[:500]); sys.exit(2)
