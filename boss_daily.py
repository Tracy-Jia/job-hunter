"""
boss_daily.py — 每日摘要 + 回复检测
用法: python boss_daily.py
输出：今日发送统计、聊天列表回复状态、跟进建议
"""
import json, time, sys, glob
from pathlib import Path
from shared import connect_chrome, load_config

SKILL_DIR = Path(__file__).parent


def scan_chat_list(page):
    """扫描聊天列表，每轮重新导航到列表页再点击"""
    conversations = []

    for i in range(25):
        page.get('https://www.zhipin.com/web/geek/chat')
        time.sleep(3)

        # 点击第i个对话
        js_click = """return (function() {
    var target = """ + str(i) + """;
    var titles = document.querySelectorAll(".title-box");
    var idx = 0;
    for (var j = 0; j < titles.length; j++) {
        if (titles[j].offsetParent && titles[j].textContent.trim().length > 2) {
            if (idx === target) {
                var name = titles[j].textContent.trim().substring(0, 60);
                var p = titles[j].closest("[class*=user-item]") || titles[j].parentElement.parentElement;
                if (p) { p.click(); return JSON.stringify({ok: true, name: name}); }
                return JSON.stringify({ok: false, reason: "no_parent"});
            }
            idx = idx + 1;
        }
    }
    return JSON.stringify({ok: false, total: idx});
})();"""
        result = page.run_js(js_click)
        info = json.loads(result)
        if not info.get('ok'):
            break
        time.sleep(0.8)

        # 检测消息状态
        js_state = """return JSON.stringify((function() {
    var myMsgs = document.querySelectorAll(".message-item.item-myself");
    var friendMsgs = document.querySelectorAll(".message-item.item-friend");
    var myC = 0, friendC = 0;
    myMsgs.forEach(function(m) { if (m.offsetParent) myC++; });
    friendMsgs.forEach(function(m) { if (m.offsetParent) friendC++; });
    var all = document.querySelectorAll(".message-item"), last = null;
    all.forEach(function(m) { if (m.offsetParent) last = m; });
    var lastMine = last ? last.className.indexOf("item-myself") >= 0 : false;
    return {my: myC, friend: friendC, lastMine: lastMine};
})());"""
        msg = json.loads(page.run_js(js_state))
        my_c, friend_c, last_mine = msg.get('my',0), msg.get('friend',0), msg.get('lastMine',False)

        state = "empty"
        if my_c > 0 and friend_c > 0 and not last_mine:
            state = "boss_replied"
        elif my_c > 0 and friend_c > 0 and last_mine:
            state = "conversation_ended"
        elif my_c > 1 and friend_c == 0:
            state = "only_me"
        elif my_c <= 1 and friend_c == 0:
            state = "default_only"
        elif friend_c > 0 and my_c <= 1:
            state = "boss_replied_no_reply"

        conversations.append({'name': info['name'], 'state': state, 'myMsgs': my_c, 'friendMsgs': friend_c})
        print(f"   [{i+1}] {state}: {info['name'][:40]} (me:{my_c}/boss:{friend_c})")

    return conversations


def load_today_sends():
    """加载今日发送记录"""
    today = time.strftime('%m%d')
    sends = []
    for lp in sorted(glob.glob(str(SKILL_DIR / f'apply-log-{today}-*.json'))):
        try:
            with open(lp, 'r', encoding='utf-8') as f:
                log = json.load(f)
            for e in log.get('sent', []):
                sends.append({'company': e.get('company','?'), 'title': e.get('title','?'),
                              'time': e.get('send_time','?'), 'source': Path(lp).name})
        except:
            pass
    return sends


def main():
    print("=" * 50)
    print("BOSS每日摘要")
    print("=" * 50)

    # 1. 今日发送
    sends = load_today_sends()
    print(f"\n[发送] 今日发送: {len(sends)} 条")
    for s in sends:
        print(f"   [{s['time']}] {s['company'][:15]} | {s['title'][:30]}")

    # 2. 聊天列表扫描
    print(f"\n[扫描] 扫描聊天列表...")
    try:
        page = connect_chrome(config=load_config())
    except Exception as e:
        print(f"   [失败] 浏览器连接失败: {e}")
        print("   请手动启动: 360ChromeX.exe --remote-debugging-port=9222")
        return

    convs = scan_chat_list(page)

    # 3. 分类
    replied = [c for c in convs if c['state'] in ('boss_replied', 'boss_replied_no_reply')]
    ongoing = [c for c in convs if c['state'] == 'conversation_ended']
    waiting = [c for c in convs if c['state'] in ('default_only', 'only_me')]

    print(f"\n[状态] 对话状态:")
    print(f"   [需跟进] 对方已回复: {len(replied)} 条")
    for c in replied:
        print(f"      {c['name'][:50]} | 我{c['myMsgs']}条/对方{c['friendMsgs']}条")

    print(f"   [已完成] 沟通完毕: {len(ongoing)} 条")
    for c in ongoing[:5]:
        print(f"      {c['name'][:50]}")

    print(f"   [等待中] 等待回复: {len(waiting)} 条")
    for c in waiting[:10]:
        print(f"      {c['name'][:50]}")

    # 4. 建议
    print(f"\n[建议] 下一步:")
    if replied:
        print(f"   优先处理 {len(replied)} 条对方已回复的对话")
    if waiting:
        print(f"   {len(waiting)} 条等待中，明天可做二次沟通")
    if len(sends) > 20:
        print(f"   今日已发 {len(sends)} 条，接近每日30条安全线")
    else:
        print(f"   今日已发 {len(sends)} 条，还有余量")


if __name__ == "__main__":
    main()
