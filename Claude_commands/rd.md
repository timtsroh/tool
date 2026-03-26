아래 작업을 순서대로 수행해줘. 추가로 묻지 말고 진행해.

---

## 1단계: 어제 날짜 보고서 확인

아래 3개 섹터의 네이버 금융 산업분석 페이지에서 어제 날짜로 올라온 보고서를 확인해.

**조선**
https://finance.naver.com/research/industry_list.naver?keyword=&brokerCode=&writeFromDate=&writeToDate=&searchType=upjong&upjong=%C1%B6%BC%B1&x=44&y=12

**반도체**
https://finance.naver.com/research/industry_list.naver?keyword=&brokerCode=&writeFromDate=&writeToDate=&searchType=upjong&upjong=%B9%DD%B5%B5%C3%BC&x=11&y=6

**에너지**
https://finance.naver.com/research/industry_list.naver?keyword=&brokerCode=&writeFromDate=&writeToDate=&searchType=upjong&upjong=%BF%A1%B3%CA%C1%F6&x=28&y=22

각 URL에 대해 아래 방법으로 파싱해:

```bash
curl -s -L --compressed \
  -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
  -H "Accept-Language: ko-KR,ko;q=0.9" \
  "<URL>" | python3 -c "
import sys, re
content = sys.stdin.buffer.read().decode('euc-kr', errors='replace')
tr_blocks = re.split(r'<tr>', content)
yesterday = '<YESTERDAY>'  # yy.mm.dd 형식
results = []
for block in tr_blocks:
    date_m = re.search(r'class=\"date\"[^>]*>(\d{2}\.\d{2}\.\d{2})</td>', block)
    if not date_m or date_m.group(1) != yesterday:
        continue
    title_m = re.search(r'<a href=\"industry_read[^\"]+\">([^<]+)</a>', block)
    broker_m = re.search(r'</td>\s*<td>([^<\n]{2,30})</td>\s*<td class=\"file\"', block)
    pdf_m = re.search(r'href=\"(https://stock\.pstatic\.net[^\"]+\.pdf)\"', block)
    title = title_m.group(1).strip() if title_m else ''
    broker = broker_m.group(1).strip() if broker_m else ''
    pdf = pdf_m.group(1) if pdf_m else ''
    if title:
        print(f'BROKER:{broker}|TITLE:{title}|PDF:{pdf}')
"
```

어제 날짜(yy.mm.dd 형식)는 오늘 날짜에서 1일 뺀 값이야. 예: 오늘이 26.03.19면 어제는 26.03.18.

각 섹터별로 PDF 링크가 있는 보고서만 다운로드 대상으로 삼아. PDF가 없는 보고서는 목록만 표시하고, 빈 .txt 파일로 저장해 (4단계 참조).

보고서 전체 제목은 개별 상세 페이지의 `<title>` 태그에서 추출해 (패턴: `조선 산업분석 - <제목> : Npay 증권`).

---

## 2단계: PDF 다운로드

다운로드 폴더:
```
/Users/tealeaf/Library/CloudStorage/GoogleDrive-taeseungg@gmail.com/My Drive/02 주식/02 자료/0 Inbox
```

PDF가 있는 보고서를 아래 명령으로 `/tmp/`에 먼저 다운로드해:

```bash
curl -L -o "/tmp/<임시파일명>.pdf" \
  -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
  "<PDF_URL>"
```

---

## 3단계: 페이지 수 확인

```python
import re

def count_pdf_pages(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()
    pages = re.findall(rb'/Type\s*/Page[^s]', content)
    if pages:
        return len(pages)
    counts = re.findall(rb'/Count\s+(\d+)', content)
    if counts:
        return max(int(c) for c in counts)
    return 0
```

---

## 4단계: 파일 이름 변경 후 최종 폴더로 이동

파일명 형식: `분류_작성일_증권사_제목_페이지수.pdf`

- **분류**: 섹터명 (조선 / 반도체 / 에너지)
- **작성일**: yy.mm.dd → yymmdd (예: 26.03.18 → 260318)
- **증권사**: 증권사명 그대로
- **제목**: 전체 제목 (콜론 `:` 제거, 특수문자 중 파일명 불가한 것 제거)
- **페이지수**: `p숫자` 형식 (예: p10)

예시: `조선_260318_신한투자증권_시황 점검 전쟁통에도 탄탄_p5.pdf`

```bash
cp "/tmp/<임시파일>.pdf" "/Users/tealeaf/Library/CloudStorage/GoogleDrive-taeseungg@gmail.com/My Drive/02 주식/02 자료/0 Inbox/<최종파일명>.pdf"
```

PDF가 없는 보고서는 빈 .txt 파일로 저장해:
- 파일명 형식: `분류_작성일_증권사_제목.txt` (페이지수 없음)
- 예시: `조선_260318_신한투자증권_시황 점검 전쟁통에도 탄탄.txt`

```bash
touch "/Users/tealeaf/Library/CloudStorage/GoogleDrive-taeseungg@gmail.com/My Drive/02 주식/02 자료/0 Inbox/<파일명>.txt"
```

---

## 5단계: 결과 요약 출력

섹터별로 처리 결과를 표로 정리해서 보여줘:
- 어제 날짜 보고서 목록 (PDF 유무 포함)
- 다운로드 및 저장된 파일명
- 저장 안 된 보고서 (PDF 없음) 별도 표시
