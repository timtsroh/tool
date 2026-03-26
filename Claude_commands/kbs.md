아래 작업을 순서대로 수행해줘. 추가로 묻지 말고 진행해.

---

## 사전 준비 확인

Playwright가 설치되어 있지 않으면 먼저 설치해:

```bash
python3 -m pip install playwright -q
python3 -m playwright install chromium
```

Facebook 로그인 세션 파일 `/Users/tealeaf/.claude/fb_session.json`이 없으면 아래를 사용자에게 안내하고 종료해:

```
Facebook 세션 파일이 없습니다.
터미널에서 /tmp/fb_login3.py를 실행하여 로그인하세요:
  python3 /tmp/fb_login3.py
```

세션 파일이 있으면 다음 단계로 진행해.

---

## 1단계: 어제 날짜 Facebook 피드 수집

```python
import asyncio, re, os
from playwright.async_api import async_playwright
from datetime import datetime, timedelta, timezone

SESSION_FILE = '/Users/tealeaf/.claude/fb_session.json'
PROFILE_URL = 'https://www.facebook.com/bongsoo2'
KST = timezone(timedelta(hours=9))

today_kst = datetime.now(KST).date()
yesterday_kst = today_kst - timedelta(days=1)
yesterday_str = yesterday_kst.strftime('%Y-%m-%d')
month_display = yesterday_kst.strftime('%y%m')

print(f'YESTERDAY:{yesterday_str}')
print(f'MONTH:{month_display}')

def parse_tooltip(tooltip):
    """'Thursday, March 19, 2026 at 2:27\u202fPM' → (date, 'HH:MM')"""
    if not tooltip:
        return None, '??:??'
    normalized = tooltip.replace('\u202f', ' ').strip()
    m = re.search(r'(\w+ \d+, \d{4}) at (\d+:\d+\s*[AP]M)', normalized, re.IGNORECASE)
    if not m:
        return None, '??:??'
    try:
        dt = datetime.strptime(f"{m.group(1)} {m.group(2).strip()}", '%B %d, %Y %I:%M %p')
        return dt.date(), dt.strftime('%H:%M')
    except:
        return None, '??:??'

def rel_to_expected_date(rel_time):
    """'1d' → date(yesterday), '2d' → date(2 days ago), '3h' → date(today or yesterday)"""
    now = datetime.now(KST)
    m = re.match(r'^(\d+)([wdhm])$', rel_time, re.IGNORECASE)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    if unit == 'd':
        return (now - timedelta(days=n)).date()
    elif unit == 'w':
        return (now - timedelta(weeks=n)).date()
    elif unit == 'h':
        return (now - timedelta(hours=n)).date()
    elif unit == 'm':
        return now.date()
    return None

async def hover_get_tooltip(page, element):
    """시간 링크에 hover해서 tooltip 텍스트 반환"""
    try:
        await page.mouse.move(640, 450)
        await page.wait_for_timeout(300)
        await element.scroll_into_view_if_needed()
        await element.hover()
        await page.wait_for_timeout(1500)
        return await page.evaluate(r"""
        () => {
            const portals = document.querySelectorAll('.__fb-light-mode [id^="_r_"], body > div[class]');
            for (const p of portals) {
                const t = p.innerText ? p.innerText.trim() : '';
                if (t.match(/\w+ \d+.*\d+:\d+/)) return t;
            }
            for (const t of document.querySelectorAll('[role="tooltip"]')) {
                if (t.innerText) return t.innerText.trim();
            }
            return null;
        }
        """)
    except:
        return None

async def get_creation_time_from_post_page(page, post_url, expected_date):
    """
    포스트 페이지의 스크립트에서 creation_time 추출.
    댓글 링크(comment_id 포함)로는 댓글 시간이 반환되므로 이 방법으로 실제 포스트 작성 시간을 구함.
    """
    try:
        await page.goto(post_url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3500)

        timestamps = await page.evaluate(r"""
        () => {
            const results = [];
            const seen = new Set();
            for (const s of document.querySelectorAll('script')) {
                const c = s.textContent || '';
                const re = /"creation_time":(\d{10})/g;
                let m;
                while ((m = re.exec(c)) !== null) {
                    const ts = parseInt(m[1]);
                    if (!seen.has(ts)) { seen.add(ts); results.push(ts); }
                }
            }
            return results.sort();
        }
        """)

        matching = []
        for ts in timestamps:
            dt = datetime.fromtimestamp(ts, tz=KST)
            if dt.date() == expected_date:
                matching.append(dt)

        if matching:
            best = min(matching)  # 해당 날짜의 가장 이른 creation_time = 원래 포스트
            return best.date(), best.strftime('%H:%M')
    except Exception as e:
        print(f'  [get_creation_time] error: {e}')

    return None, '??:??'

async def get_posts():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            storage_state=SESSION_FILE,
            viewport={'width': 1280, 'height': 900},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        await page.goto(PROFILE_URL, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(5000)

        seen_keys = set()
        all_posts = []

        for scroll_n in range(25):
            # JS로 See more 클릭 + 포스트 수집
            result = await page.evaluate(r"""
            () => {
                const stories = document.querySelectorAll('[data-ad-rendering-role="story_message"]');
                const posts = [];

                stories.forEach(story => {
                    // See more 버튼 클릭
                    const seeMoreBtn = story.querySelector('div[role="button"]');
                    if (seeMoreBtn) {
                        const btnText = seeMoreBtn.innerText ? seeMoreBtn.innerText.trim() : '';
                        if (btnText === 'See more' || btnText === '더 보기') {
                            seeMoreBtn.click();
                        }
                    }

                    const text = story.innerText ? story.innerText.trim() : '';
                    const key = text.substring(0, 40);

                    // 시간 링크 찾기 (DOM 위로 탐색)
                    let card = story;
                    let timeInfo = null;
                    for (let i = 0; i < 25; i++) {
                        card = card.parentElement;
                        if (!card) break;
                        for (const a of card.querySelectorAll('a')) {
                            const t = a.innerText ? a.innerText.trim() : '';
                            if (/^\d+[wdhm]$/i.test(t)) {
                                timeInfo = {
                                    text: t,
                                    href: a.href,
                                    hasCommentId: a.href.includes('comment_id'),
                                };
                                break;
                            }
                        }
                        if (timeInfo) break;
                    }

                    posts.push({
                        key,
                        text,
                        timeInfo,
                    });
                });
                return posts;
            }
            """)

            await page.wait_for_timeout(800)  # See more 확장 대기

            # 확장된 텍스트 재수집
            stories_els = await page.query_selector_all('[data-ad-rendering-role="story_message"]')
            expanded = {}
            for el in stories_els:
                t = await el.inner_text()
                if t:
                    t = t.strip()
                    for r in result:
                        if r['key'][:20] in t:
                            expanded[r['key']] = t
                            break

            found_older = False
            for pi in result:
                if pi['key'] in seen_keys or not pi['text']:
                    continue
                seen_keys.add(pi['key'])

                text = expanded.get(pi['key'], pi['text'])
                ti = pi.get('timeInfo') or {}
                rel_time = ti.get('text') or ''
                has_comment_id = ti.get('hasCommentId', False)
                href = ti.get('href') or ''

                expected_date = rel_to_expected_date(rel_time) if rel_time else None

                if expected_date and expected_date < yesterday_kst:
                    found_older = True
                    continue

                post_date, time_str = None, '??:??'

                if has_comment_id and expected_date and href:
                    # comment_id가 있는 경우: hover tooltip은 댓글 시간을 반환 → 포스트 페이지에서 creation_time 추출
                    base_url = href.split('?')[0]
                    print(f'  [comment_id link] fetching post page for creation_time...')
                    post_date, time_str = await get_creation_time_from_post_page(page, base_url, expected_date)
                    # 포스트 페이지 탐색 후 프로필 페이지로 복귀
                    await page.goto(PROFILE_URL, wait_until='domcontentloaded', timeout=60000)
                    await page.wait_for_timeout(3000)
                    # 스크롤 상태 복구 불가 → 다음 scroll 루프에서 재수집
                    seen_keys.discard(pi['key'])  # 재수집 허용
                    # creation_time으로 날짜/시간을 얻었으면 바로 저장
                    if post_date:
                        all_posts.append({
                            'key': pi['key'],
                            'text': text,
                            'post_date': post_date,
                            'time_str': time_str,
                            'rel_time': rel_time,
                        })
                        seen_keys.add(pi['key'])
                    break  # 루프 재시작
                else:
                    # comment_id 없는 경우: hover tooltip 사용
                    for el in stories_els:
                        el_t = await el.inner_text()
                        if el_t and pi['key'][:20] in el_t.strip():
                            time_a = await el.evaluate_handle(r"""
                            el => {
                                let card = el;
                                for (let i = 0; i < 25; i++) {
                                    card = card.parentElement;
                                    if (!card) break;
                                    for (const a of card.querySelectorAll('a')) {
                                        const t = a.innerText ? a.innerText.trim() : '';
                                        if (/^\d+[wdhm]$/i.test(t)) return a;
                                    }
                                }
                                return null;
                            }
                            """)
                            is_null = await time_a.evaluate("el => el === null")
                            if not is_null:
                                tooltip = await hover_get_tooltip(page, time_a)
                                post_date, time_str = parse_tooltip(tooltip)
                            break

                all_posts.append({
                    'key': pi['key'],
                    'text': text,
                    'post_date': post_date,
                    'time_str': time_str,
                    'rel_time': rel_time,
                })

            dates = [p['post_date'] for p in all_posts if p['post_date']]
            oldest = min(dates) if dates else None
            print(f'SCROLL:{scroll_n} TOTAL:{len(all_posts)} OLDEST:{oldest}')

            if found_older:
                print('Found posts older than yesterday, stopping')
                break

            await page.evaluate('window.scrollBy(0, 2000)')
            await page.wait_for_timeout(2500)

        await browser.close()
        return all_posts

all_posts = asyncio.run(get_posts())
filtered_posts = [p for p in all_posts if p.get('post_date') == yesterday_kst]

print(f'COUNT:{len(filtered_posts)}')
for p in filtered_posts:
    print('---POST---')
    print(f'TIME:{p["time_str"]}')
    print(p['text'])
```

피드가 0개면 "어제 올라온 글 없음"을 출력하고 종료해.

---

## 2단계: 포스트 요약 생성

수집된 각 포스트 내용을 읽고, **핵심을 5단어 이내 한국어**로 요약해.
요약은 명사 위주로, 조사는 최소화하여 간결하게 작성해.
filtered_posts의 각 항목에 `'summary'` 키로 추가해.

예시:
- "VLCC 운임 폭등 신조 확산"
- "달리오 호르무즈 미국 패권 경고"

---

## 3단계: Obsidian 노트 생성/업데이트

**저장 경로:**
```
/Users/tealeaf/Library/Mobile Documents/iCloud~md~obsidian/Documents/CC/0 inbox
```

**노트 파일명 형식:** `김봉수_월.md`
- 월: yyMM (예: 2603)
- 동일 월 노트가 이미 있으면 기존 파일에 **추가(append)**

예시: `김봉수_2603.md`

**노트 내용 형식 (신규 생성 시):**

```markdown
---
tags: [김봉수, 페이스북]
month: YYYY-MM
source: https://www.facebook.com/bongsoo2
---

# 김봉수 2603

---
#### YYYY-MM-DD · HH:MM · <5단어 이내 요약>

<첫 번째 피드 내용>

---
#### YYYY-MM-DD · HH:MM · <5단어 이내 요약>

<두 번째 피드 내용>
```

**기존 노트에 추가 시:** 파일 끝에 `---` 구분선과 함께 새 글 append.

노트 생성/업데이트:

```python
import os

VAULT = "/Users/tealeaf/Library/Mobile Documents/iCloud~md~obsidian/Documents/CC/0 inbox"

filename = f"김봉수_{month_display}.md"
filepath = os.path.join(VAULT, filename)

if os.path.exists(filepath):
    # 기존 파일에 추가
    with open(filepath, 'a', encoding='utf-8') as f:
        for post in filtered_posts:
            f.write(f"\n---\n#### {yesterday_str} · {post['time_str']} · {post['summary']}\n\n{post['text']}\n")
else:
    # 신규 생성
    year_month = yesterday_kst.strftime('%Y-%m')
    lines = [
        "---",
        "tags: [김봉수, 페이스북]",
        f"month: {year_month}",
        "source: https://www.facebook.com/bongsoo2",
        "---",
        "",
        f"# 김봉수 {month_display}",
        "",
    ]
    for i, post in enumerate(filtered_posts):
        if i > 0:
            lines.append("---")
            lines.append("")
        lines.append(f"#### {yesterday_str} · {post['time_str']}")
        lines.append("")
        lines.append(post['text'])
        lines.append("")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

print(f"✓ 저장: {filename}")
```

---

## 3단계: 결과 요약 출력

- 수집된 피드 수
- 저장/업데이트된 노트 파일명 및 경로
- 각 피드 시간 및 첫 줄 미리보기

---

## ⚠️ 참고: 시간 표시 방식

- 시간 링크에 `comment_id` 없음 → hover tooltip으로 정확한 HH:MM 추출
- 시간 링크에 `comment_id` 포함 → 포스트 페이지의 `creation_time` 스크립트 데이터에서 추출 (댓글 시간이 아닌 원본 포스트 작성 시간)
- creation_time도 없을 경우 → `??:??` 표시

## ⚠️ 세션 만료 시 재로그인

Facebook 세션이 만료되면 사용자 터미널에서 실행:

```bash
python3 /tmp/fb_login3.py
```
