아래 작업을 순서대로 수행해줘. 추가로 묻지 말고 진행해.

---

## 1단계: 어제 날짜 텔레그램 피드 수집

Telethon을 사용해서 어제 날짜로 올라온 글을 수집해.

```python
import asyncio
from telethon import TelegramClient
from telethon.tl.types import (
    MessageEntityTextUrl, MessageEntityUrl,
    MessageEntityBold, MessageEntityItalic, MessageEntityUnderline,
    MessageEntityCode, MessageEntityPre
)
from datetime import datetime, timedelta, timezone

API_ID = 32844347
API_HASH = '432b3c2ca6b5e925320031c3e234ac58'
SESSION_FILE = '/Users/tealeaf/.claude/tg_session'
CHANNEL = 'chunjonghyun'

def build_markdown(text, entities):
    """entities를 활용해 마크다운 텍스트 생성 (링크 포함)"""
    if not entities:
        return text

    # 오프셋 기준으로 정렬
    sorted_ents = sorted(entities, key=lambda e: e.offset)
    result = ''
    prev = 0
    for ent in sorted_ents:
        start = ent.offset
        end = ent.offset + ent.length
        chunk = text[start:end]
        result += text[prev:start]
        if isinstance(ent, MessageEntityTextUrl):
            result += f'[{chunk}]({ent.url})'
        elif isinstance(ent, MessageEntityUrl):
            result += f'[{chunk}]({chunk})'
        elif isinstance(ent, MessageEntityBold):
            result += f'**{chunk}**'
        elif isinstance(ent, MessageEntityItalic):
            result += f'*{chunk}*'
        elif isinstance(ent, MessageEntityUnderline):
            result += f'**{chunk}**'
        elif isinstance(ent, (MessageEntityCode, MessageEntityPre)):
            result += f'`{chunk}`'
        else:
            result += chunk
        prev = end
    result += text[prev:]
    return result

async def main():
    # 어제 날짜 계산 (KST = UTC+9)
    kst = timezone(timedelta(hours=9))
    today_kst = datetime.now(kst).date()
    yesterday_kst = today_kst - timedelta(days=1)
    yesterday_str = yesterday_kst.strftime('%Y-%m-%d')
    yesterday_display = yesterday_kst.strftime('%y%m%d')
    year_month = yesterday_kst.strftime('%y%m')

    print(f'YESTERDAY_ISO:{yesterday_str}')
    print(f'YESTERDAY_DISPLAY:{yesterday_display}')
    print(f'YEAR_MONTH:{year_month}')

    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.connect()

    # 채널 메시지 수집 (최근 200개에서 어제 날짜 필터링)
    messages = []
    async for msg in client.iter_messages(CHANNEL, limit=200):
        msg_date = msg.date.astimezone(kst).date()
        if msg_date == yesterday_kst:
            messages.append(msg)
        elif msg_date < yesterday_kst:
            break  # 더 이전 날짜면 중단

    messages.reverse()  # 오래된 것부터 정렬

    print(f'COUNT:{len(messages)}')

    seen = set()
    for msg in messages:
        if not msg.text:
            continue

        # 중복 제거
        key = msg.text[:30]
        if key in seen:
            continue
        seen.add(key)

        # Forwarded from 처리
        forwarded = ''
        if msg.forward:
            fwd = msg.forward
            if hasattr(fwd, 'channel_id') and fwd.channel_id:
                try:
                    fwd_entity = await client.get_entity(fwd.channel_id)
                    fwd_name = getattr(fwd_entity, 'title', '') or getattr(fwd_entity, 'username', '')
                    fwd_username = getattr(fwd_entity, 'username', '')
                    fwd_url = f'https://t.me/{fwd_username}' if fwd_username else ''
                    forwarded = f'FORWARDED:{fwd_name}|{fwd_url}'
                except:
                    forwarded = 'FORWARDED:Unknown|'
            elif hasattr(fwd, 'from_name') and fwd.from_name:
                forwarded = f'FORWARDED:{fwd.from_name}|'

        # KST 시간
        time_kst = msg.date.astimezone(kst).strftime('%H:%M')

        # 텍스트 + 링크 마크다운 변환
        md_text = build_markdown(msg.text, msg.entities)

        print('---MSG---')
        print(f'TIME:{time_kst}')
        if forwarded:
            print(forwarded)
        print(md_text)

    await client.disconnect()

asyncio.run(main())
```

수집된 피드를 순서대로 정리해. 피드가 0개면 "어제 올라온 글 없음"을 출력하고 종료해.

---

## 2단계: Obsidian 월별 노트에 추가

**저장 경로:**
```
/Users/tealeaf/Library/Mobile Documents/iCloud~md~obsidian/Documents/CC/0 inbox
```

**노트 파일명 형식:** `전종현_년월.md`
- 년월: yymm (예: 2603)

예시: `전종현_2603.md`

**처리 로직:**

- 파일이 **없으면**: 새로 생성 (frontmatter + 제목 포함)
- 파일이 **있으면**: 기존 내용을 읽고, 어제 날짜의 새 항목을 날짜순·시간순에 맞는 위치에 삽입

**날짜 구분선 형식:** `## YYYY-MM-DD`

각 날짜 섹션 내에서 `#### HH:MM 핵심내용 요약` 항목은 시간 오름차순으로 정렬.

**새 파일 생성 시 내용 형식:**

```markdown
---
tags: [전종현, 텔레그램, 산업분석]
date: YYYY-MM
source: https://t.me/chunjonghyun
---

# 전종현 2603

---
## YYYY-MM-DD

#### HH:MM 핵심내용 요약
<피드 내용>

---
#### HH:MM 핵심내용 요약
> Forwarded from [채널명](링크)

<피드 내용 — forwarded인 경우>
```

**기존 파일에 추가 시:**

1. 파일 전체를 읽는다
2. 어제 날짜(`## YYYY-MM-DD`) 섹션이 있으면 → 해당 섹션 내 마지막 항목 뒤에 새 항목 추가
3. 어제 날짜 섹션이 없으면 → 날짜순에 맞는 위치에 새 섹션(`## YYYY-MM-DD`) 삽입 후 항목 추가
4. 이미 동일한 시간(`#### HH:MM`)의 항목이 있으면 중복이므로 건너뜀

**공통 규칙:**
- 각 피드 상단에 KST 시간을 `#### HH:MM 핵심내용 요약` 형식으로 표시 (핵심내용은 해당 피드의 주요 내용을 5단어 이내로 요약)
- Forwarded 메시지는 시간 아래에 `> Forwarded from [채널명](링크)` 인용 블록 추가
- 본문 내 링크는 `[텍스트](URL)` Markdown 형식으로 유지
- 피드 간 구분은 `---` 수평선 사용

노트 저장 시 Python으로 파일을 직접 write해:

```python
import os

VAULT = "/Users/tealeaf/Library/Mobile Documents/iCloud~md~obsidian/Documents/CC/0 inbox"
filepath = f"{VAULT}/{filename}.md"

if os.path.exists(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        existing = f.read()
    # 기존 내용에 새 항목 삽입 (날짜순·시간순)
    updated = merge_entries(existing, new_entries, yesterday_str)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(updated)
else:
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
```

---

## 3단계: 결과 요약 출력

- 수집된 피드 수
- 생성/업데이트된 노트 파일명 및 경로
- 신규 생성인지 기존 파일 업데이트인지 표시
- 각 피드 첫 줄 미리보기 (forwarded 여부 포함)
