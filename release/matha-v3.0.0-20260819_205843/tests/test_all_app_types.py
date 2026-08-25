"""Matha 全类型应用构建能力测试 — 游戏/社交/工具/影音/购物/生活/教育/新闻/工业/安全/平台."""
import os, sys, glob, tempfile

sys.path.insert(0, r"D:\trae")
from src.codegen import codegen
from src.interp import interpret

PASS, FAIL = [], []

def test(name, ok, detail=""):
    if ok:
        PASS.append(name)
        print(f"  ✓ {name}{detail}")
    else:
        FAIL.append(name)
        print(f"  ✗ {name}{detail}")

# ============================================================
# 1. Matha 解释器核心
# ============================================================
print("\n【1. 解释器核心】")
interp_tests = [
    ("算术", "#1：[3 + 4 * 2]", 11),
    ("函数", "func 加(a: Int, b: Int) -> Int = (a, b) => a + b\n#1：[加(3)(4)]", 7),
    ("递归", "func 阶乘(n: Int) -> Int = (n) => (n <= 1) ? 1 : n * 阶乘(n - 1)\n#1：[阶乘(5)]", 120),
    ("三角", "#1：[sin(3.14159/6)]", 0.5),
    ("对数", "#1：[exp(1.0)]", 2.718),
]
for name, src, expected in interp_tests:
    try:
        out, _ = interpret(src)
        actual = out[0] if isinstance(out, list) else out
        test(name, abs(actual - expected) < 0.5, f" → {out}")
    except Exception as e:
        test(name, False, f": {e}")

# ============================================================
# 2. 游戏应用构建
# ============================================================
print("\n【2. 游戏应用】")
def gen(name, spec, out_dir):
    try:
        r = codegen(spec, out_dir)
        if not r.成功:
            test(name, False, f": {r.错误}")
            return False
        test(name, True, f" → {r.文件}")
        return True
    except Exception as e:
        test(name, False, f": {e}")
        return False

gen("游戏-贪吃蛇", [
    "应用", "游戏", "贪吃蛇",
    [["角色", "snake", []], ["收集", "food", []], ["文字", "得分: 0", []]],
    [["宽度", "400"], ["高度", "400"], ["帧率", "10"], ["背景", "#222"], ["标题", "贪吃蛇"]]
], "D:/trae/_test_output/game_snake")

gen("游戏-赛车", [
    "应用", "游戏", "赛车",
    [["角色", "car", []], ["敌人", "obstacle", []], ["收集", "coin", []],
     ["文字", "速度: 0", []]],
    [["宽度", "800"], ["高度", "600"], ["帧率", "60"], ["背景", "#333"], ["标题", "赛车"]]
], "D:/trae/_test_output/game_racing")

gen("游戏-塔防", [
    "应用", "游戏", "塔防",
    [["角色", "tower", []], ["敌人", "enemy", []], ["收集", "coin", []],
     ["文字", "生命: 100", []]],
    [["宽度", "800"], ["高度", "600"], ["帧率", "30"], ["背景", "#2a5"], ["标题", "塔防"]]
], "D:/trae/_test_output/game_td")

# ============================================================
# 3. 社交应用构建
# ============================================================
print("\n【3. 社交应用】")
gen("社交-即时通讯", [
    "应用", "网页", "即时通讯",
    [
        ["div", "", [["id", "chat-container"]], [
            ["div", "", [["id", "message-list"]], []],
            ["input", "", [["id", "message-input"]], []],
            ["button", "发送", [["onclick", "sendMessage()"]], []],
        ]],
    ],
    [["宽度", "600"], ["标题", "即时通讯"]]
], "D:/trae/_test_output/social_chat")

gen("社交-朋友圈", [
    "应用", "网页", "朋友圈",
    [
        ["div", "", [["id", "feed"]], [
            ["div", "用户A: 今天天气很好", [["class", "post"]], []],
            ["div", "用户B: 吃了吗", [["class", "post"]], []],
        ]],
        ["input", "", [["id", "post-input"]], []],
        ["button", "发布", [["onclick", "post()"]], []],
    ],
    [["宽度", "500"], ["标题", "朋友圈"]]
], "D:/trae/_test_output/social_feed")

gen("社交-直播间", [
    "应用", "网页", "直播间",
    [
        ["video", "", [["id", "stream"], ["autoplay", "true"]], []],
        ["div", "", [["id", "chat-box"]], []],
        ["input", "", [["id", "chat-input"]], []],
        ["button", "送礼", [["onclick", "sendGift()"]], []],
    ],
    [["宽度", "900"], ["标题", "直播间"]]
], "D:/trae/_test_output/social_live")

# ============================================================
# 4. 日常工具应用
# ============================================================
print("\n【4. 日常工具应用】")
gen("工具-计算器", [
    "应用", "桌面", "计算器",
    [
        ["input", "", [["id", "display"], ["readonly", "true"]], []],
        ["button", "C", [["onclick", "clear_display"]], []],
        ["button", "1", [["onclick", "append('1')"]], []],
        ["button", "=", [["onclick", "calculate()"]], []],
    ],
    [["尺寸", "320x400"], ["标题", "计算器"]]
], "D:/trae/_test_output/tool_calc")

gen("工具-天气查询", [
    "应用", "网页", "天气查询",
    [
        ["input", "", [["id", "city"], ["placeholder", "输入城市"]], []],
        ["button", "查询", [["onclick", "query_weather()"]], []],
        ["div", "", [["id", "weather-result"]], []],
    ],
    [["宽度", "400"], ["标题", "天气查询"]]
], "D:/trae/_test_output/tool_weather")

gen("工具-单位换算", [
    "应用", "桌面", "单位换算",
    [
        ["input", "", [["id", "value"], ["width", "10"]], []],
        ["select", "", [["id", "from_unit"]], []],
        ["select", "", [["id", "to_unit"]], []],
        ["button", "换算", [["onclick", "convert()"]], []],
        ["label", "结果:", [["id", "result"]], []],
    ],
    [["尺寸", "400x300"], ["标题", "单位换算"]]
], "D:/trae/_test_output/tool_unit")

# ============================================================
# 5. 影音播放应用
# ============================================================
print("\n【5. 影音播放应用】")
gen("影音-音乐播放器", [
    "应用", "网页", "音乐播放器",
    [
        ["audio", "", [["id", "player"], ["controls", "true"]], []],
        ["button", "播放", [["onclick", "play()"]], []],
        ["button", "暂停", [["onclick", "pause()"]], []],
        ["input", "", [["id", "volume"], ["type", "range"], ["min", "0"], ["max", "100"]]],
        ["div", "播放列表", [["id", "playlist"]], []],
    ],
    [["宽度", "400"], ["标题", "音乐播放器"]]
], "D:/trae/_test_output/media_player")

gen("影音-视频播放器", [
    "应用", "网页", "视频播放器",
    [
        ["video", "", [["id", "player"], ["controls", "true"], ["width", "640"]], []],
        ["button", "播放", [["onclick", "play()"]], []],
        ["button", "全屏", [["onclick", "fullscreen()"]], []],
        ["input", "", [["id", "progress"], ["type", "range"]]],
    ],
    [["宽度", "700"], ["标题", "视频播放器"]]
], "D:/trae/_test_output/media_video")

gen("影音-音频编辑器", [
    "应用", "桌面", "音频编辑器",
    [
        ["canvas", "", [["id", "waveform"], ["width", "800"], ["height", "200"]], []],
        ["button", "播放", [["onclick", "play_wave()"]], []],
        ["button", "录音", [["onclick", "record()"]], []],
        ["button", "导出", [["onclick", "export()"]], []],
    ],
    [["尺寸", "850x300"], ["标题", "音频编辑器"]]
], "D:/trae/_test_output/media_editor")

# ============================================================
# 6. 购物支付应用
# ============================================================
print("\n【6. 购物支付应用】")
gen("购物-商品列表", [
    "应用", "网页", "商品列表",
    [
        ["div", "", [["id", "products"]], [
            ["div", "商品A ¥99", [["class", "product"]], []],
            ["div", "商品B ¥199", [["class", "product"]], []],
        ]],
        ["button", "加入购物车", [["onclick", "add_to_cart()"]], []],
        ["div", "购物车: 0", [["id", "cart"]], []],
    ],
    [["宽度", "600"], ["标题", "购物"]]
], "D:/trae/_test_output/shop_list")

gen("购物-购物车", [
    "应用", "网页", "购物车",
    [
        ["table", "", [["id", "cart-items"]], []],
        ["div", "合计: ¥0", [["id", "total"]], []],
        ["button", "结算", [["onclick", "checkout()"]], []],
    ],
    [["宽度", "500"], ["标题", "购物车"]]
], "D:/trae/_test_output/shop_cart")

gen("购物-支付页面", [
    "应用", "网页", "支付页面",
    [
        ["h1", "确认支付", [], []],
        ["div", "金额: ¥299", [["id", "amount"]], []],
        ["select", "", [["id", "payment_method"]], [
            ["option", "微信支付", []],
            ["option", "支付宝", []],
            ["option", "银行卡", []],
        ]],
        ["button", "确认支付", [["onclick", "pay()"]], []],
    ],
    [["宽度", "400"], ["标题", "支付页面"]]
], "D:/trae/_test_output/shop_pay")

# ============================================================
# 7. 生活服务应用
# ============================================================
print("\n【7. 生活服务应用】")
gen("生活服务-外卖", [
    "应用", "网页", "外卖点餐",
    [
        ["div", "餐厅列表", [["id", "restaurants"]], []],
        ["div", "购物车", [["id", "cart"]], []],
        ["button", "下单", [["onclick", "order()"]], []],
        ["div", "预计送达: 30分钟", [["id", "eta"]], []],
    ],
    [["宽度", "600"], ["标题", "外卖点餐"]]
], "D:/trae/_test_output/life_food")

gen("生活服务-出行", [
    "应用", "网页", "出行导航",
    [
        ["input", "", [["id", "start"], ["placeholder", "起点"]], []],
        ["input", "", [["id", "end"], ["placeholder", "终点"]], []],
        ["button", "导航", [["onclick", "navigate()"]], []],
        ["div", "", [["id", "route"]], []],
    ],
    [["宽度", "600"], ["标题", "出行导航"]]
], "D:/trae/_test_output/life_nav")

gen("生活服务-健康管理", [
    "应用", "桌面", "健康管理",
    [
        ["input", "", [["id", "weight"], ["placeholder", "体重(kg)"]], []],
        ["input", "", [["id", "height"], ["placeholder", "身高(cm)"]], []],
        ["button", "计算BMI", [["onclick", "calc_bmi()"]], []],
        ["label", "BMI结果:", [["id", "bmi_result"]], []],
        ["canvas", "", [["id", "chart"], ["width", "400"], ["height", "200"]], []],
    ],
    [["尺寸", "450x350"], ["标题", "健康管理"]]
], "D:/trae/_test_output/life_health")

# ============================================================
# 8. 教育学习应用
# ============================================================
print("\n【8. 教育学习应用】")
gen("教育-在线课程", [
    "应用", "网页", "在线课程",
    [
        ["div", "课程列表", [["id", "courses"]], []],
        ["div", "", [["id", "video-player"]], []],
        ["button", "开始学习", [["onclick", "start_course()"]], []],
        ["div", "进度: 0%", [["id", "progress"]], []],
    ],
    [["宽度", "800"], ["标题", "在线课程"]]
], "D:/trae/_test_output/edu_course")

gen("教育-考试系统", [
    "应用", "网页", "在线考试",
    [
        ["div", "", [["id", "question"]], []],
        ["button", "A", [["onclick", "select('A')"]], []],
        ["button", "B", [["onclick", "select('B')"]], []],
        ["button", "C", [["onclick", "select('C')"]], []],
        ["button", "D", [["onclick", "select('D')"]], []],
        ["button", "提交", [["onclick", "submit()"]], []],
    ],
    [["宽度", "600"], ["标题", "在线考试"]]
], "D:/trae/_test_output/edu_exam")

gen("教育-词汇背诵", [
    "应用", "桌面", "词汇背诵",
    [
        ["label", "单词:", [["id", "word"]], []],
        ["label", "释义:", [["id", "definition"]], []],
        ["button", "认识", [["onclick", "known()"]], []],
        ["button", "不认识", [["onclick", "unknown()"]], []],
        ["label", "正确率:", [["id", "accuracy"]], []],
    ],
    [["尺寸", "400x300"], ["标题", "词汇背诵"]]
], "D:/trae/_test_output/edu_vocab")

# ============================================================
# 9. 新闻阅读应用
# ============================================================
print("\n【9. 新闻阅读应用】")
gen("新闻-新闻聚合", [
    "应用", "网页", "新闻聚合",
    [
        ["div", "头条", [["id", "headline"]], []],
        ["div", "", [["id", "news-list"]], []],
        ["input", "", [["id", "search"], ["placeholder", "搜索新闻"]], []],
        ["button", "分类", [["onclick", "filter_category()"]], []],
    ],
    [["宽度", "800"], ["标题", "新闻聚合"]]
], "D:/trae/_test_output/news_aggregate")

gen("新闻-阅读APP", [
    "应用", "网页", "阅读APP",
    [
        ["div", "文章列表", [["id", "articles"]], []],
        ["div", "", [["id", "article-content"]], []],
        ["button", "上一篇文章", [["onclick", "prev_article()"]], []],
        ["button", "下一篇文章", [["onclick", "next_article()"]], []],
        ["input", "", [["id", "bookmark"], ["placeholder", "书签"]]],
    ],
    [["宽度", "600"], ["标题", "阅读APP"]]
], "D:/trae/_test_output/news_reader")

gen("新闻- RSS订阅", [
    "应用", "桌面", "RSS订阅",
    [
        ["input", "", [["id", "feed_url"], ["width", "40"]], []],
        ["button", "添加订阅", [["onclick", "add_feed()"]], []],
        ["list", "", [["id", "feeds"]], []],
        ["label", "最新: 0条", [["id", "count"]], []],
    ],
    [["尺寸", "500x400"], ["标题", "RSS订阅"]]
], "D:/trae/_test_output/news_rss")

# ============================================================
# 10. 基础软件/后台服务
# ============================================================
print("\n【10. 基础软件】")
gen("服务-用户API", [
    "应用", "服务", "用户API",
    [
        ["接口", "GET", "/api/users", "list_users"],
        ["接口", "POST", "/api/users", "create_user"],
        ["接口", "GET", "/api/users/{id}", "get_user"],
        ["接口", "DELETE", "/api/users/{id}", "delete_user"],
    ],
    [["端口", "8080"]]
], "D:/trae/_test_output/service_users")

gen("服务-数据API", [
    "应用", "服务", "数据分析API",
    [
        ["接口", "GET", "/api/stats", "get_stats"],
        ["接口", "POST", "/api/upload", "upload_data"],
        ["接口", "GET", "/api/download/{id}", "download_data"],
    ],
    [["端口", "8081"]]
], "D:/trae/_test_output/service_data")

# ============================================================
# 11. 3D建模
# ============================================================
print("\n【11. 3D建模】")
def check_threejs(d):
    html = os.path.join(d, "index.html")
    if not os.path.exists(html): return False
    with open(html, encoding="utf-8") as f:
        return "three" in f.read().lower()

gen("3D-建筑模型", [
    "应用", "建模", "建筑模型",
    [
        ["球体", "穹顶", {"r": 2, "颜色": "#8B4513", "材质": "标准"}],
        ["球体", "塔楼", {"r": 0.5, "颜色": "#666", "材质": "金属"}],
        ["光源", "环境光", {"type": "ambient"}],
        ["光源", "方向光", {"type": "directional"}],
    ],
    [["宽度", "800"], ["高度", "600"], ["动画", "旋转"], ["标题", "建筑模型"]]
], "D:/trae/_test_output/3d_building")
test("3D-建筑模型-Three.js", check_threejs("D:/trae/_test_output/3d_building"), " ✓")

gen("3D-分子模型", [
    "应用", "建模", "DNA分子",
    [
        ["球体", "磷酸", {"r": 0.2, "颜色": "#FF0000"}],
        ["球体", "碱基", {"r": 0.3, "颜色": "#0000FF"}],
        ["球体", "糖", {"r": 0.15, "颜色": "#00FF00"}],
        ["光源", "环境光", {"type": "ambient"}],
    ],
    [["宽度", "800"], ["高度", "600"], ["动画", "旋转"], ["标题", "DNA分子"]]
], "D:/trae/_test_output/3d_dna")
test("3D-DNA-Three.js", check_threejs("D:/trae/_test_output/3d_dna"), " ✓")

# ============================================================
# 12. 系统脚本
# ============================================================
print("\n【12. 系统脚本】")
gen("系统-数据库备份", [
    "应用", "系统", "数据库备份",
    [
        ["endpoint", "exec", "/backup", "mkdir -p /backup && echo 'backup done'"],
        ["endpoint", "exec", "/restore", "echo 'restoring...'"],
        ["endpoint", "file", "/status", "echo 'DB healthy'"],
    ],
    []
], "D:/trae/_test_output/sys_backup")

gen("系统-日志清理", [
    "应用", "系统", "日志清理",
    [
        ["endpoint", "exec", "/clean", "find /var/log -mtime +7 -delete"],
        ["endpoint", "file", "/report", "echo 'cleaned' > /tmp/clean_report"],
    ],
    []
], "D:/trae/_test_output/sys_logs")

# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 70)
total = len(PASS) + len(FAIL)
print(f"总计: {len(PASS)}/{total} 通过")
if not FAIL:
    print("所有构建测试通过 ✓")
else:
    print(f"失败 ({len(FAIL)} 个): {', '.join(FAIL)}")
print("=" * 70)

# 资源库统计
print("\n【资源库统计】")
counts = {
    "resource": len(glob.glob("matha/resource/**/*.matha", recursive=True)),
    "knowledge": len(glob.glob("matha/knowledge/**/*.matha", recursive=True)),
    "library": len(glob.glob("matha/library/**/*.matha", recursive=True)),
}
for k, v in counts.items():
    print(f"  {k}: {v} 文件")

# 新增模块
new_modules = glob.glob("matha/resource/**/*.matha", recursive=True)
print(f"\n【新增模块 ({len(new_modules)} 个)】")
for f in sorted(new_modules):
    rel = f.replace(chr(92), "/")
    print(f"  {rel}")

print("=" * 70)
sys.exit(0 if not FAIL else 1)
