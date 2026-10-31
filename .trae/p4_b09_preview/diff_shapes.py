import json

a = json.load(open(r"D:\trae\.trae\p4_b09_preview\ws_off.json", encoding="utf-8"))
b = json.load(open(r"D:\trae\.trae\p4_b09_preview\ws_on.json", encoding="utf-8"))
for k in a["cases"]:
    oa, ob = a["cases"][k]["call_argcs"], b["cases"][k]["call_argcs"]
    codes_same = json.dumps(a["cases"][k]["codes"]) == json.dumps(b["cases"][k]["codes"])
    print(f"{k:20s} OFF={oa} ON={ob} shape_diff={not codes_same}")
