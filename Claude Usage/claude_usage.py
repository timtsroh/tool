#!/usr/bin/env python3
"""Claude Usage Monitor — claude.ai 실시간 사용량 (5시간/7일 카운트다운)"""

import tkinter as tk
import json, os, re, subprocess, shutil, tempfile, sqlite3, hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

HELPER     = str(Path(__file__).parent / "claude_fetch_helper")
CACHE_FILE = str(Path(__file__).parent / ".claude_usage_cache.json")
REFRESH_MS = 30_000   # 30초마다 API 갱신
TICK_MS    = 1_000    # 1초마다 카운트다운 업데이트

# ── 색상 ─────────────────────────────────────────────────────
BG      = "#0d1117"
BG2     = "#161b22"
BG3     = "#21262d"
BORDER  = "#30363d"
TEXT    = "#e6edf3"
DIM     = "#7d8590"
GREEN   = "#3fb950"
YELLOW  = "#d29922"
ORANGE  = "#db6d28"
RED     = "#f85149"
BLUE    = "#58a6ff"
PURPLE  = "#bc8cff"


def load_cache():
    """캐시 파일에서 session/org_id 로드"""
    try:
        with open(CACHE_FILE, "r") as f:
            d = json.load(f)
            return d.get("session"), d.get("org_id")
    except:
        return None, None


def save_cache(session, org_id):
    """session/org_id를 캐시 파일에 저장"""
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({"session": session, "org_id": org_id}, f)
    except:
        pass


def get_chrome_cookies():
    """Chrome 쿠키에서 sessionKey, orgId 추출 후 캐시 저장"""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-w", "-a", "Chrome", "-s", "Chrome Safe Storage"],
            capture_output=True, text=True
        )
        password = result.stdout.strip()
        if not password:
            return None, None

        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

        key = hashlib.pbkdf2_hmac("sha1", password.encode(), b"saltysalt", 1003, dklen=16)

        def decrypt(enc):
            try:
                if enc[:3] != b"v10": return None
                iv = b" " * 16
                c = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
                d = c.decryptor()
                raw = d.update(enc[3:]) + d.finalize()
                pad = raw[-1]; raw = raw[:-pad]
                idx = raw.find(b"\x60")
                return raw[idx+1:].decode("utf-8", errors="ignore") if idx >= 0 else raw.decode("utf-8", errors="ignore")
            except: return None

        db_path = Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies"
        tmp = tempfile.mktemp(suffix=".db")
        shutil.copy2(str(db_path), tmp)
        conn = sqlite3.connect(tmp)
        cookies = {}
        for name, enc in conn.execute(
            "SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%claude.ai%'"
        ):
            val = decrypt(enc)
            if val: cookies[name] = val
        conn.close(); os.unlink(tmp)

        session_raw = cookies.get("sessionKey", "")
        org_raw = cookies.get("lastActiveOrg", "")
        m1 = re.search(r"sk-ant-sid\S+", session_raw)
        m2 = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", org_raw)
        session = m1.group(0) if m1 else None
        org_id  = m2.group(0) if m2 else None
        if session and org_id:
            save_cache(session, org_id)
        return session, org_id
    except Exception:
        return None, None


def fetch_usage(session, org_id):
    """Swift 헬퍼로 claude.ai API 호출"""
    try:
        r = subprocess.run(
            [HELPER, session, org_id],
            capture_output=True, text=True, timeout=15
        )
        return json.loads(r.stdout)
    except Exception as e:
        return {"error": str(e)}


def utilization_color(pct):
    if pct < 50:   return GREEN
    if pct < 75:   return YELLOW
    if pct < 90:   return ORANGE
    return RED


def fmt_countdown(dt_reset):
    now = datetime.now(timezone.utc)
    remaining = dt_reset - now
    if remaining.total_seconds() <= 0:
        return "00:00:00", 0
    total = int(remaining.total_seconds())
    h, m, s = total // 3600, (total % 3600) // 60, total % 60
    return f"{h:02d}:{m:02d}", total


def parse_reset(resets_at_str):
    if not resets_at_str: return None
    try:
        return datetime.fromisoformat(resets_at_str)
    except:
        return None


# ── App ──────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Claude Usage")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.attributes("-topmost", True)

        self._data = {}
        self._session = None
        self._org_id  = None
        self._five_reset = None
        self._seven_reset = None
        self._last_error = ""

        self._drag_x = self._drag_y = 0
        self._build_ui()

        # 초기 로딩
        self._load_credentials()
        self._fetch()
        self._tick()

    # ── 자격증명 ──────────────────────────────────────────────
    def _load_credentials(self):
        # 캐시 먼저 시도 → 없으면 Chrome 쿠키에서 직접 추출
        session, org_id = load_cache()
        if not session or not org_id:
            session, org_id = get_chrome_cookies()
        self._session, self._org_id = session, org_id

    # ── UI ────────────────────────────────────────────────────
    def _build_ui(self):
        # 타이틀 바
        bar = tk.Frame(self, bg=BG2, cursor="fleur")
        bar.pack(fill="x")
        bar.bind("<ButtonPress-1>",  self._drag_start)
        bar.bind("<B1-Motion>",      self._drag_move)

        tk.Label(bar, text="  ◆ Claude Usage", bg=BG2, fg=BLUE,
                 font=("SF Pro Display", 10, "bold"), anchor="w").pack(side="left", padx=4, pady=6)

        tk.Label(bar, text="✕", bg=BG2, fg=DIM, font=("SF Pro Display", 12),
                 cursor="hand2").pack(side="right", padx=10)
        bar.winfo_children()[-1].bind("<Button-1>", lambda e: self.destroy())

        # 메인
        main = tk.Frame(self, bg=BG, padx=18, pady=14)
        main.pack(fill="both", expand=True)

        # ── 5시간 섹션 ─────────────────────────────────────
        tk.Label(main, text="5시간 리셋까지", bg=BG, fg=DIM,
                 font=("SF Pro Display", 9)).pack()

        self.cd_lbl = tk.Label(main, text="--:--", bg=BG, fg=GREEN,
                                font=("SF Mono", 26, "bold"))
        self.cd_lbl.pack(pady=(0, 2))

        self.reset_lbl = tk.Label(main, text="", bg=BG, fg=DIM, font=("SF Pro Display", 12))
        self.reset_lbl.pack()

        self._sep(main)

        # 5시간 프로그레스
        f5 = tk.Frame(main, bg=BG); f5.pack(fill="x", pady=(0, 8))
        row1 = tk.Frame(f5, bg=BG); row1.pack(fill="x")
        tk.Label(row1, text="5h 사용률", bg=BG, fg=DIM, font=("SF Pro Display", 11), anchor="w").pack(side="left")
        self.pct5_lbl = tk.Label(row1, text="—", bg=BG, fg=TEXT, font=("SF Mono", 20, "bold"), anchor="e")
        self.pct5_lbl.pack(side="right")

        self.bar5 = self._make_bar(f5, height=14)

        # ── 7일 섹션 ───────────────────────────────────────
        self._sep(main)
        f7 = tk.Frame(main, bg=BG); f7.pack(fill="x", pady=(0, 8))
        row2 = tk.Frame(f7, bg=BG); row2.pack(fill="x")
        tk.Label(row2, text="7일 사용률", bg=BG, fg=DIM, font=("SF Pro Display", 11), anchor="w").pack(side="left")
        self.pct7_lbl = tk.Label(row2, text="—", bg=BG, fg=TEXT, font=("SF Mono", 20, "bold"), anchor="e")
        self.pct7_lbl.pack(side="right")
        self.bar7 = self._make_bar(f7, height=14)
        self.reset7_lbl = tk.Label(f7, text="", bg=BG, fg=DIM, font=("SF Pro Display", 9), anchor="w")
        self.reset7_lbl.pack(fill="x", pady=(2, 0))

        # ── 하단 ───────────────────────────────────────────
        self._sep(main)
        self.status_lbl = tk.Label(main, text="불러오는 중...", bg=BG, fg=DIM,
                                    font=("SF Pro Display", 8))
        self.status_lbl.pack()

    def _sep(self, parent):
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=8)

    def _make_bar(self, parent, height=7):
        c = tk.Canvas(parent, bg=BG3, height=height, bd=0, highlightthickness=0)
        c.pack(fill="x", expand=True, pady=(6, 0))
        bar = c.create_rectangle(0, 0, 0, height, fill=GREEN, outline="")
        # 창 크기 변경 시 바 자동 업데이트
        c.bind("<Configure>", lambda e, c=c, b=bar, h=height: self._on_bar_resize(e, c, b, h))
        return (c, bar, height)

    def _on_bar_resize(self, event, canvas, bar, height):
        # 현재 저장된 pct/color로 바 다시 그리기
        pct5 = getattr(self, "_five_pct", 0) or 0
        pct7 = getattr(self, "_seven_pct", 0) or 0
        if hasattr(self, "bar5") and canvas is self.bar5[0]:
            pct, color = pct5, utilization_color(pct5)
        elif hasattr(self, "bar7") and canvas is self.bar7[0]:
            pct, color = pct7, utilization_color(pct7)
        else:
            return
        fill_w = int(event.width * min(pct / 100.0, 1.0))
        canvas.itemconfig(bar, fill=color)
        canvas.coords(bar, 0, 0, fill_w, height)

    def _update_bar(self, bar_tuple, pct, color):
        canvas, bar, height = bar_tuple
        canvas.update_idletasks()
        w = canvas.winfo_width() or 270
        fill_w = int(w * min(pct / 100.0, 1.0))
        canvas.itemconfig(bar, fill=color)
        canvas.coords(bar, 0, 0, fill_w, height)

    # ── 드래그 ────────────────────────────────────────────────
    def _drag_start(self, e):
        self._drag_x = e.x_root - self.winfo_x()
        self._drag_y = e.y_root - self.winfo_y()

    def _drag_move(self, e):
        self.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")

    # ── 데이터 갱신 ───────────────────────────────────────────
    def _fetch(self):
        """API에서 데이터 가져오기 (30초마다)"""
        if not self._session or not self._org_id:
            self._load_credentials()

        if self._session and self._org_id:
            data = fetch_usage(self._session, self._org_id)
            if "error" not in data:
                self._data = data
                fh = data.get("five_hour") or {}
                sd = data.get("seven_day") or {}
                self._five_reset  = parse_reset(fh.get("resets_at"))
                self._seven_reset = parse_reset(sd.get("resets_at"))
                self._five_pct    = fh.get("utilization", 0) or 0
                self._seven_pct   = sd.get("utilization", 0) or 0
                self._last_error  = ""
                self._update_static_labels()
            else:
                self._last_error = data.get("error", "API 오류")
        else:
            self._last_error = "Chrome 세션 없음"

        self.after(REFRESH_MS, self._fetch)

    def _update_static_labels(self):
        """30초 갱신 항목 업데이트"""
        pct5 = self._five_pct
        pct7 = self._seven_pct
        c5 = utilization_color(pct5)
        c7 = utilization_color(pct7)

        self.pct5_lbl.config(text=f"{pct5:.0f}%", fg=c5)
        self.pct7_lbl.config(text=f"{pct7:.0f}%", fg=c7)
        self._update_bar(self.bar5, pct5, c5)
        self._update_bar(self.bar7, pct7, c7)

        if self._seven_reset:
            kst = timezone(timedelta(hours=9))
            r7_kst = self._seven_reset.astimezone(kst)
            self.reset7_lbl.config(text=f"7일 리셋: {r7_kst.strftime('%m/%d %H:%M')} KST")

    def _tick(self):
        """1초마다 카운트다운 업데이트"""
        if self._five_reset:
            txt, secs = fmt_countdown(self._five_reset)
            if secs > 3600:   color = GREEN
            elif secs > 1200: color = YELLOW
            elif secs > 0:    color = RED
            else:             color = DIM; txt = "00:00"

            self.cd_lbl.config(text=txt, fg=color)

            kst = timezone(timedelta(hours=9))
            r_kst = self._five_reset.astimezone(kst)
            self.reset_lbl.config(text=f"리셋: {r_kst.strftime('%H:%M:%S')} KST")
        else:
            self.cd_lbl.config(text="--:--", fg=DIM)
            self.reset_lbl.config(text=self._last_error or "데이터 없음", fg=RED if self._last_error else DIM)

        now_str = datetime.now().strftime("%H:%M:%S")
        self.status_lbl.config(text=f"갱신: {now_str}  |  30초마다 자동 갱신")

        self.after(TICK_MS, self._tick)


if __name__ == "__main__":
    app = App()
    app.update_idletasks()
    sw = app.winfo_screenwidth()
    app.geometry(f"205x366+{sw - 205}+25")
    app.mainloop()
