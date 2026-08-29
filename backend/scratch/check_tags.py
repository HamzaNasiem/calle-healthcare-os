with open("dashboard/src/pages/Settings.jsx", "r", encoding="utf-8") as f:
    lines = f.readlines()

open_divs = []
for i, line in enumerate(lines, 1):
    # simple token count
    # count occurrences of <div and </div
    import re
    opens = len(re.findall(r'<div[\s/>]', line))
    closes = len(re.findall(r'</div>', line))
    self_closes = len(re.findall(r'<div[^>]*/>', line))
    opens -= self_closes
    if opens > 0:
        for _ in range(opens):
            open_divs.append(i)
    if closes > 0:
        for _ in range(closes):
            if open_divs:
                open_divs.pop()
            else:
                print(f"Extra closing div at line {i}: {line.strip()}")

print(f"Total unclosed divs: {len(open_divs)}")
if open_divs:
    print(f"Lines with unclosed divs: {open_divs}")
