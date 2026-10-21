"""微信批量触达 · 从原始发送记录复算全部统计。

为什么要有这个脚本：
  作品集里那张「目标 / 已送达 / 未送达 / 送达率」的表，如果只是一个手填的数字表，
  任何人都无法核对。这个脚本从原始 CSV 复算，同样的输入得到同样的输出——
  「可验证」和「我记下来了」是两件事。

数据来源：E:\\wechatauto\\work 下的发送记录（本人账号，内部效率工具，不对外）
用法：
  python stats.py                     # 打印统计
  python stats.py --sample 20         # 导出 20 条脱敏样例，用于公开分享
"""
import argparse
import collections
import csv
import io
import os
import re

DATA = r"E:\wechatauto\work"
HERE = os.path.dirname(os.path.abspath(__file__))

GROUPS = [
    ("转发", "转发_发送记录.csv"),
    ("数据中心群发用", "数据中心群发用_发送记录.csv"),
    ("标签1", "标签1_发送记录.csv"),
]

# 短名 / 英文名：微信搜索会命中多人，系统拒发转人工
# 判据：纯英文串（不论长短，如 Sunny / Qing / H）、或 1–2 个汉字的昵称（如 原 / 阳光）
ENGLISH_NAME = re.compile(r"^[A-Za-z][A-Za-z .\-]{0,20}$")
# 公司名而非个人：含行业词、公司后缀
COMPANY_HINT = re.compile(
    r"泵业|科技|装备|铝业|集团|公司|股份|实业|制造|电子|化工|材料|"
    r"TOPSFLO|Inc\.?|Ltd\.?|Co\.?", re.I
)


def load(name):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return None
    raw = open(p, encoding="utf-8-sig", errors="replace").read()
    return list(csv.DictReader(io.StringIO(raw)))


def classify(rows):
    """把未送达的按类别归因。这是「宁可少发，不可错发」那条规则的实证。"""
    cats = collections.Counter()
    detail = collections.defaultdict(list)
    for r in rows:
        name = (r.get("姓名") or "").strip()
        status = (r.get("状态") or "").strip()
        if status == "已送达":
            continue
        head = name.split()[0] if name else ""
        if COMPANY_HINT.search(name):
            k = "名称是公司而非个人"
        elif ENGLISH_NAME.match(head) or len(head) <= 2:
            k = "短名 / 英文名 / 昵称歧义"
        else:
            k = "其他（名称与微信显示名不一致）"
        cats[k] += 1
        detail[k].append(name)
    return cats, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0, help="导出 N 条脱敏样例到 sample_sent.csv")
    args = ap.parse_args()

    print("=" * 66)
    print("微信批量触达 · 从原始发送记录复算")
    print("=" * 66)
    print(f"{'组':16s} {'目标':>6s} {'已送达':>7s} {'未完成':>7s} {'送达率':>8s} {'状态':>6s}")
    print("-" * 66)

    total = collections.Counter()
    all_rows = []
    for label, fn in GROUPS:
        rows = load(fn)
        if rows is None:
            print(f"{label:16s}   [未找到 {fn}]")
            continue
        c = collections.Counter((r.get("状态") or "").strip() for r in rows)
        ok = c.get("已送达", 0)
        n = len(rows)
        total.update(c)
        all_rows.extend(rows)
        print(f"{label:16s} {n:>6d} {ok:>7d} {n - ok:>7d} {ok / n * 100:>7.1f}% {len(c):>6d}")

    n = sum(total.values())
    ok = total.get("已送达", 0)
    print("-" * 66)
    print(f"{'合计':16s} {n:>6d} {ok:>7d} {n - ok:>7d} {ok / n * 100:>7.1f}%")

    # 已完成的两组（标签1 仍在分批中，未完成不等于失败）
    done_rows = []
    for label in ("转发", "数据中心群发用"):
        rows = load(dict((l, f) for l, f in GROUPS)[label])
        if rows:
            done_rows.extend(rows)
    d_ok = sum(1 for r in done_rows if (r.get("状态") or "").strip() == "已送达")
    print(f"\n已完成两组（转发 + 数据中心）：{len(done_rows)} 目标 / {d_ok} 送达 / "
          f"{len(done_rows) - d_ok} 未送达（{(len(done_rows) - d_ok) / len(done_rows) * 100:.1f}%）")

    cats, detail = classify(done_rows)
    print(f"\n=== 未送达归因（{sum(cats.values())} 人）===")
    for k, v in cats.most_common():
        print(f"  {k:24s} {v:>3d}   {', '.join(detail[k][:6])}")

    members = load("标签成员.csv")
    if members:
        tags = collections.Counter((r.get("标签名") or "").strip() for r in members)
        print(f"\n=== 标签池 ===")
        print(f"  联系人 {len(members)} 人 / {len(tags)} 个标签")
        for k, v in tags.most_common(8):
            print(f"    {v:>5d}  {k}")

    if args.sample:
        out = os.path.join(HERE, "sample_sent.csv")
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["姓名", "wxid", "状态"])
            for i, r in enumerate(all_rows[:args.sample], 1):
                # 完全脱敏：原姓名不保留任何片段（含手机号、字母、行业词）
                w.writerow([f"联系人{i:03d}", f"wxid_sample_{i:03d}", (r.get("状态") or "").strip()])
        print(f"\n已导出脱敏样例 → {out}（{args.sample} 条，姓名与 wxid 均已替换为编号）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
