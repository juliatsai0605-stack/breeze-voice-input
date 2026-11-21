"""微風語音輸入 Breeze Voice Input（Windows 工作列版）

https://github.com/juliatsai0605-stack/breeze-voice-input

熱鍵（可在設定視窗修改）：
  按住 右Ctrl  照講的打字
  按住 F9      講口語 → AI 整理成正式文字
  按住 F7      講中文 → AI 翻譯
  F8           開始／結束長段口述（停頓數秒自動結束）
  F10          先選取打錯的字，按 F10 說出正確的詞 → 取代並記進名詞表
工作列圖示右下角小圓點：灰＝載入中、綠＝待命、紅＝錄音中、橘＝處理中、藍＝暫停。雙擊圖示開設定視窗。
資料位置：%LOCALAPPDATA%/BreezeVoiceInput（可用環境變數 BREEZE_VOICE_HOME 改）
"""
import json
import logging
import os
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.request
import winsound
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import numpy as np

APP_DIR = Path(__file__).resolve().parent.parent
_home_arg = sys.argv[sys.argv.index("--home") + 1] if "--home" in sys.argv[:-1] else None
ROOT = Path(_home_arg or os.environ.get("BREEZE_VOICE_HOME")
            or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "BreezeVoiceInput")
ROOT.mkdir(parents=True, exist_ok=True)
if (ROOT / "hf-cache").is_dir():  # 資料夾裡已有模型快取就沿用，不重複下載
    os.environ.setdefault("HF_HOME", str(ROOT / "hf-cache"))
ICON_PNG = APP_DIR / "assets" / "icon.png"
ICON_ICO = APP_DIR / "assets" / "icon.ico"
CONFIG = ROOT / "config.json"
GLOSSARY = ROOT / "glossary.txt"
if not GLOSSARY.exists() and (APP_DIR / "glossary.sample.txt").exists():
    GLOSSARY.write_text((APP_DIR / "glossary.sample.txt").read_text(encoding="utf-8"), encoding="utf-8")
SR = 16000
logging.basicConfig(filename=ROOT / "app.log", level=logging.INFO, encoding="utf-8",
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("voice")

DEFAULTS = {
    "hotkey_dictate": "right ctrl",
    "hotkey_rewrite": "f9",
    "hotkey_translate": "f7",
    "hotkey_toggle": "f8",
    "hotkey_glossary": "f10",
    "auto_stop": True,
    "silence_sec": 2.5,
    "beep": True,
    "punctuation": True,
    "llm_backend": "ollama",
    "lmstudio_model": "qwen/qwen3.5-9b",
    "ollama_model": "qwen3:8b",
    "rewrite_style": "通順的書面語，刪掉口頭語與重複",
    "translate_target": "英文",
    "num_beams": 3,
}

HALLUCINATIONS = ["謝謝收看", "謝謝觀看", "請訂閱", "訂閱", "字幕由", "字幕提供", "Amara.org", "明鏡與點點",
                  "感謝收看", "請不吝點贊"]
PUNCS = "，。？！、；："


def load_config():
    cfg = dict(DEFAULTS)
    if CONFIG.exists():
        try:
            cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
        except Exception:
            log.exception("config 讀取失敗，使用預設值")
    return cfg


def save_config(cfg):
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")


def load_glossary():
    terms, fixes = [], []
    if GLOSSARY.exists():
        for line in GLOSSARY.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=>" in line:
                a, b = [x.strip() for x in line.split("=>", 1)]
                if a and b:
                    fixes.append((a, b))
            else:
                terms.append(line)
    return terms, fixes


# ───────────────────────── 辨識 ─────────────────────────
class Recognizer:
    def __init__(self, cfg):
        import torch
        from funasr import AutoModel
        from opencc import OpenCC
        from transformers import WhisperForConditionalGeneration, WhisperProcessor

        self.torch = torch
        self.cfg = cfg
        mid = "MediaTek-Research/Breeze-ASR-25"
        self.proc = WhisperProcessor.from_pretrained(mid)
        self.model = WhisperForConditionalGeneration.from_pretrained(mid, dtype=torch.float16).to("cuda").eval()
        self.cc = OpenCC("s2twp")
        self.t2s = OpenCC("t2s")
        self.punc = AutoModel(model="ct-punc", hub="hf", device="cuda:0", disable_update=True)
        self.reload_glossary()
        self.transcribe(np.zeros(SR, dtype=np.float32))

    def reload_glossary(self):
        terms, self.fixes = load_glossary()
        head = "以下是繁體中文的句子，中英夾雜，有標點符號。"
        picked = []
        for t in terms:  # Whisper 提示上限約 224 token，保留餘裕
            trial = head + "、".join(picked + [t]) + "。"
            if len(self.proc.tokenizer.encode(trial, add_special_tokens=False)) > 180:
                break
            picked.append(t)
        self.prompt_text = head + "、".join(picked) + "。"
        self.prompt_ids = self.proc.get_prompt_ids(self.prompt_text, return_tensors="pt").to("cuda")

    def transcribe(self, audio, punctuate=None):
        torch = self.torch
        pieces = [audio[i:i + 28 * SR] for i in range(0, len(audio), 28 * SR)] or [audio]
        texts = []
        for p in pieces:
            feats = self.proc(p, sampling_rate=SR, return_tensors="pt").input_features.to("cuda", torch.float16)
            with torch.no_grad():
                ids = self.model.generate(feats, language="zh", task="transcribe", prompt_ids=self.prompt_ids,
                                          num_beams=int(self.cfg["num_beams"]), max_new_tokens=220)
            texts.append(self.proc.batch_decode(ids, skip_special_tokens=True)[0])
        text = self.clean("".join(texts))
        if punctuate if punctuate is not None else self.cfg["punctuation"]:
            text = self.punctuate(text)
        return text

    def clean(self, text):
        text = text.replace(self.prompt_text, "")
        text = self.cc.convert(text)
        for h in HALLUCINATIONS:
            text = text.replace(h, "")
        for a, b in self.fixes:
            text = text.replace(a, b)
        text = re.sub(r"(.{2,}?)\1{2,}", r"\1", text)
        text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text.strip())
        return text

    def punctuate(self, text):
        if not text or any(p in text for p in PUNCS):
            return text
        try:
            simp = self.t2s.convert(text)
            if len(simp) != len(text):
                return text
            res = self.punc.generate(input=simp)[0]["text"]
        except Exception:
            log.exception("標點失敗")
            return text
        out, i = [], 0
        for ch in res:
            while i < len(text) and text[i].isspace() and not ch.isspace():
                out.append(text[i]); i += 1
            if ch in PUNCS:
                out.append(ch)
            elif i < len(text) and ch.lower() == simp[i].lower():
                out.append(text[i]); i += 1
            elif ch.strip() == "":
                continue
            else:
                return text
        out.append(text[i:])
        return "".join(out)


# ───────────────────────── AI 改寫／翻譯 ─────────────────────────
LMS = Path.home() / ".lmstudio" / "bin" / "lms.exe"


def lmstudio_up():
    try:
        with urllib.request.urlopen("http://127.0.0.1:1234/v1/models", timeout=3):
            return True
    except Exception:
        return False


def ensure_lmstudio(cfg):
    """LM Studio 沒開時，用它的命令列在背景啟動伺服器並載入模型（不開視窗、不重複下載）。"""
    model = cfg.get("lmstudio_model", "qwen/qwen3.5-9b")
    hidden = 0x08000000
    if not lmstudio_up():
        log.info("LM Studio 未啟動，改用背景啟動")
        subprocess.run([str(LMS), "server", "start"], capture_output=True, timeout=120, creationflags=hidden)
        for _ in range(60):
            if lmstudio_up():
                break
            time.sleep(1)
        else:
            raise RuntimeError("LM Studio 背景啟動失敗")
    ps = subprocess.run([str(LMS), "ps"], capture_output=True, text=True, encoding="utf-8",
                        timeout=30, creationflags=hidden).stdout
    if model not in ps:
        log.info("載入 LM Studio 模型 %s", model)
        subprocess.run([str(LMS), "load", model, "--yes"], capture_output=True, timeout=300, creationflags=hidden)


def ask_llm(cfg, system, user):
    if cfg["llm_backend"] == "lmstudio":
        ensure_lmstudio(cfg)
    if cfg["llm_backend"] == "claude":
        prompt = f"{system}\n\n---\n{user}"
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
        r = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, encoding="utf-8",
                           timeout=120, creationflags=0x08000000, env=env)
        out = r.stdout.strip()
        if r.returncode != 0 or not out:
            msg = (r.stderr or r.stdout or "").strip()
            if "auth" in msg.lower() or "login" in msg.lower():
                msg = "Claude 未登入：請開 PowerShell 輸入 claude，再輸入 /login 重新登入"
            raise RuntimeError(msg or "Claude 沒有回應")
    elif cfg["llm_backend"] == "lmstudio":
        body = json.dumps({
            "model": cfg.get("lmstudio_model", "qwen/qwen3.5-9b"), "temperature": 0.2, "stream": False,
            "chat_template_kwargs": {"enable_thinking": False}, "reasoning_effort": "none",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:1234/v1/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                out = json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"] or ""
        except urllib.error.URLError:
            raise RuntimeError("LM Studio 沒有開：請打開 LM Studio 並啟動本機伺服器")
    else:
        body = json.dumps({
            "model": cfg["ollama_model"], "stream": False, "think": False, "keep_alive": "2h",
            "options": {"temperature": 0.2},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                out = json.loads(resp.read().decode("utf-8"))["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise RuntimeError(f"Ollama 裡沒有模型 {cfg['ollama_model']}：請執行 ollama pull {cfg['ollama_model']}")
            raise
        except urllib.error.URLError:
            raise RuntimeError("Ollama 沒有開：請啟動 Ollama")
    out = re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()
    return out.strip("「」\"' \n")


def rewrite(cfg, text, cc):
    system = (f"你是文字整理助手。把使用者的口述整理成{cfg['rewrite_style']}。"
              "規則：只輸出整理後的文字，不要標題、說明或引號；不得新增口述中沒有的事實、數字、人名、日期；"
              "專有名詞與英文術語照原樣保留；使用繁體中文（台灣用語）。")
    return cc.convert(ask_llm(cfg, system, text))


def translate(cfg, text):
    system = f"把使用者給的文字翻譯成{cfg['translate_target']}。只輸出譯文，不要任何說明。專有名詞保留正確寫法。"
    return ask_llm(cfg, system, text)


# ───────────────────────── 錄音與熱鍵 ─────────────────────────
class Engine:
    def __init__(self, ui_queue):
        self.cfg = load_config()
        self.q = ui_queue
        self.rec = None
        self.frames = []
        self.recording = False
        self.mode = None          # dictate / rewrite / translate / glossary
        self.hands_free = False   # F8／F10：按一下開始，再按或靜音自動停
        self.paused = False
        self.last_voice = 0.0
        self.start_time = 0.0
        self.glossary_wrong = ""
        self.lock = threading.Lock()
        self.hooks = []

    # 狀態回報給視窗與圖示
    def status(self, state, msg=""):
        log.info("[%s] %s", state, msg)
        self.q.put(("status", state, msg))

    def result(self, mode, text, extra=""):
        self.q.put(("result", mode, text, extra))

    def beep(self, f, d=80):
        if self.cfg["beep"]:
            winsound.Beep(f, d)

    def load_models(self):
        self.status("loading", "載入模型中（約 20～30 秒）…")
        try:
            self.rec = Recognizer(self.cfg)
        except Exception as e:
            log.exception("模型載入失敗")
            self.status("error", f"模型載入失敗：{e}")
            return
        self.bind_hotkeys()
        self.beep(1000, 150)
        self.status("ready", "待命中")
        if self.cfg["llm_backend"] in ("ollama", "lmstudio"):  # 預先載入本機 AI，第一次整理才不用等
            threading.Thread(target=self.warm_llm, daemon=True).start()

    def warm_llm(self):
        try:
            ask_llm(self.cfg, "只回答：好", "好")
            log.info("本機 AI 已預先載入")
        except Exception as e:
            log.warning("本機 AI 預先載入失敗：%s", e)
            self.status("ready", f"待命中（F9／F7 暫不可用：{e}）")

    # 熱鍵
    def bind_hotkeys(self):
        import keyboard
        for h in self.hooks:
            try:
                keyboard.unhook(h)
            except Exception:
                pass
        self.hooks = []
        c = self.cfg

        def hold(key, mode):
            self.hooks.append(keyboard.on_press_key(key, lambda e: self.start(mode), suppress=key.startswith("f")))
            self.hooks.append(keyboard.on_release_key(key, lambda e: self.stop_if(mode, hands_free=False),
                                                      suppress=key.startswith("f")))

        hold(c["hotkey_dictate"], "dictate")
        hold(c["hotkey_rewrite"], "rewrite")
        hold(c["hotkey_translate"], "translate")
        self.hooks.append(keyboard.on_press_key(c["hotkey_toggle"], lambda e: self.toggle("dictate"), suppress=True))
        self.hooks.append(keyboard.on_press_key(c["hotkey_glossary"], lambda e: self.toggle("glossary"), suppress=True))

    def toggle(self, mode):
        if self.recording and self.hands_free:
            self.stop()
        elif not self.recording:
            if mode == "glossary":
                self.glossary_wrong = self.copy_selection()
                if not self.glossary_wrong:
                    self.status("ready", "新增名詞：請先選取打錯的字，再按熱鍵")
                    self.beep(300, 200)
                    return
            self.start(mode, hands_free=True)

    def start(self, mode, hands_free=False):
        if self.paused or self.rec is None:
            return
        with self.lock:
            if self.recording:
                return
            self.frames, self.recording, self.mode, self.hands_free = [], True, mode, hands_free
            self.start_time = self.last_voice = time.time()
        self.beep(880)
        label = {"dictate": "照講的打", "rewrite": "整理成正式文字", "translate": "翻譯",
                 "glossary": f"說出「{self.glossary_wrong}」的正確寫法"}[mode]
        self.status("recording", f"錄音中：{label}")

    def stop_if(self, mode, hands_free):
        if self.recording and self.mode == mode and self.hands_free == hands_free:
            self.stop()

    def stop(self):
        with self.lock:
            if not self.recording:
                return
            self.recording = False
            frames, mode = self.frames, self.mode
        self.beep(600)
        threading.Thread(target=self.finish, args=(frames, mode), daemon=True).start()

    def audio_cb(self, indata, frames, t, status):
        if not self.recording:
            return
        chunk = indata[:, 0].copy()
        self.frames.append(chunk)
        now = time.time()
        if float(np.sqrt(np.mean(chunk ** 2))) > 0.01:
            self.last_voice = now
        if (self.hands_free and self.cfg["auto_stop"] and now - self.start_time > 1.0
                and now - self.last_voice > float(self.cfg["silence_sec"])):
            threading.Thread(target=self.stop, daemon=True).start()

    def finish(self, frames, mode):
        if not frames:
            self.status("ready", "待命中")
            return
        audio = np.concatenate(frames).astype(np.float32)
        dur = len(audio) / SR
        if dur < 0.4 or float(np.sqrt(np.mean(audio ** 2))) < 0.004:
            self.status("ready", f"略過：{dur:.1f} 秒，太短或太小聲")
            return
        self.status("busy", "辨識中…")
        t0 = time.time()
        try:
            if mode == "glossary":
                right = re.sub(f"[{PUNCS}。.,!?\\s]", "", self.rec.transcribe(audio, punctuate=False))
                if right and right != self.glossary_wrong:
                    with GLOSSARY.open("a", encoding="utf-8") as f:
                        f.write(f"\n{self.glossary_wrong} => {right}")
                    self.rec.reload_glossary()
                    self.paste(right)
                    self.result(mode, right, f"已記入名詞表：{self.glossary_wrong} => {right}")
                else:
                    self.status("ready", "沒聽清楚正確的詞，名詞表未變更")
                    return
            else:
                raw = self.rec.transcribe(audio)
                out = raw
                if raw and mode == "rewrite":
                    self.status("busy", "AI 整理中…")
                    out = rewrite(self.cfg, raw, self.rec.cc)
                elif raw and mode == "translate":
                    self.status("busy", "AI 翻譯中…")
                    out = translate(self.cfg, raw)
                if out:
                    self.paste(out)
                self.result(mode, out, raw if out != raw else "")
            self.status("ready", f"完成（{dur:.1f} 秒語音，處理 {time.time() - t0:.1f} 秒）")
        except Exception as e:
            log.exception("處理失敗")
            self.status("ready", f"失敗：{e}")
            self.beep(300, 300)

    # 剪貼簿
    def copy_selection(self):
        import keyboard
        import pyperclip
        try:
            old = pyperclip.paste()
        except Exception:
            old = ""
        pyperclip.copy("")
        keyboard.send("ctrl+c")
        time.sleep(0.15)
        sel = pyperclip.paste().strip()
        pyperclip.copy(old)
        return sel

    def paste(self, text):
        import keyboard
        import pyperclip
        try:
            old = pyperclip.paste()
        except Exception:
            old = None
        pyperclip.copy(text)
        time.sleep(0.05)
        keyboard.send("ctrl+v")
        time.sleep(0.3)
        if old is not None:
            pyperclip.copy(old)


# ───────────────────────── 視窗與工作列圖示 ─────────────────────────
COLORS = {"loading": "#9e9e9e", "ready": "#2e9d4e", "recording": "#d93025", "busy": "#f29900",
          "paused": "#1a73e8", "error": "#5f6368"}
STATE_NAMES = {"loading": "載入中", "ready": "待命", "recording": "錄音中", "busy": "處理中",
               "paused": "暫停", "error": "錯誤"}
MODE_NAMES = {"dictate": "照講", "rewrite": "整理", "translate": "翻譯", "glossary": "名詞"}


def make_icon(color):
    from PIL import Image, ImageDraw
    if ICON_PNG.exists():
        img = Image.open(ICON_PNG).convert("RGBA").resize((64, 64), Image.LANCZOS)
    else:
        img = Image.new("RGBA", (64, 64), (37, 99, 235, 255))
    d = ImageDraw.Draw(img)
    d.ellipse((40, 40, 63, 63), fill=color, outline="white", width=3)
    return img


class App:
    def __init__(self):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk = tk, ttk
        self.q = queue.Queue()
        self.engine = Engine(self.q)
        self.state = "loading"

        self.root = tk.Tk()
        self.root.title("微風語音輸入")
        if ICON_ICO.exists():
            try:
                self.root.iconbitmap(str(ICON_ICO))
            except Exception:
                pass
        self.root.geometry("640x560")
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self.build_ui()

        import pystray
        self.icon = pystray.Icon("voice", make_icon(COLORS["loading"]), "微風語音輸入：載入中", menu=pystray.Menu(
            pystray.MenuItem("開啟視窗", lambda: self.q.put(("show",)), default=True),
            pystray.MenuItem("暫停／恢復", lambda: self.q.put(("pause",))),
            pystray.MenuItem("結束", lambda: self.q.put(("quit",))),
        ))
        self.icon.run_detached()

        threading.Thread(target=self.start_audio, daemon=True).start()
        self.root.after(100, self.poll)
        if os.environ.get("VOICE_APP_HIDDEN") == "1" or "--hidden" in sys.argv:
            self.root.withdraw()

    def start_audio(self):
        import sounddevice as sd
        self.engine.load_models()
        try:
            self.stream = sd.InputStream(samplerate=SR, channels=1, dtype="float32", callback=self.engine.audio_cb)
            self.stream.start()
        except Exception as e:
            log.exception("麥克風開啟失敗")
            self.q.put(("status", "error", f"麥克風開啟失敗：{e}"))

    # UI
    def build_ui(self):
        tk, ttk = self.tk, self.ttk
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # 狀態頁
        f1 = ttk.Frame(nb, padding=10); nb.add(f1, text="狀態與紀錄")
        self.status_var = tk.StringVar(value="載入中…")
        ttk.Label(f1, textvariable=self.status_var, font=("Microsoft JhengHei UI", 12, "bold")).pack(anchor="w")
        self.help_var = tk.StringVar()
        ttk.Label(f1, textvariable=self.help_var, foreground="#555", justify="left").pack(anchor="w", pady=(4, 8))
        self.history = tk.Listbox(f1, font=("Microsoft JhengHei UI", 10))
        self.history.pack(fill="both", expand=True)
        row = ttk.Frame(f1); row.pack(fill="x", pady=(6, 0))
        ttk.Button(row, text="複製選取的紀錄", command=self.copy_history).pack(side="left")
        ttk.Button(row, text="暫停／恢復", command=self.toggle_pause).pack(side="left", padx=6)
        ttk.Button(row, text="縮到工作列", command=self.hide).pack(side="right")
        self.items = []

        # 設定頁
        f2 = ttk.Frame(nb, padding=10); nb.add(f2, text="設定")
        c = self.engine.cfg
        self.vars = {}
        fields = [
            ("hotkey_dictate", "照講的打（按住）"), ("hotkey_rewrite", "整理成正式文字（按住）"),
            ("hotkey_translate", "翻譯（按住）"), ("hotkey_toggle", "長段口述（按一下開始／結束）"),
            ("hotkey_glossary", "新增名詞（先選取錯字再按）"), ("silence_sec", "停頓幾秒自動結束"),
            ("rewrite_style", "整理成什麼風格"), ("translate_target", "翻譯成哪種語言"),
            ("lmstudio_model", "LM Studio 模型名稱"), ("ollama_model", "Ollama 模型名稱"), ("num_beams", "辨識精細度（1 快～5 準）"),
        ]
        for i, (k, label) in enumerate(fields):
            ttk.Label(f2, text=label).grid(row=i, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=str(c[k])); self.vars[k] = v
            ttk.Entry(f2, textvariable=v, width=44).grid(row=i, column=1, sticky="we", pady=3)
        n = len(fields)
        self.backend = tk.StringVar(value=c["llm_backend"])
        ttk.Label(f2, text="AI 整理／翻譯用").grid(row=n, column=0, sticky="w", pady=3)
        bf = ttk.Frame(f2); bf.grid(row=n, column=1, sticky="w")
        ttk.Radiobutton(bf, text="LM Studio（本機）", variable=self.backend, value="lmstudio").pack(side="left")
        ttk.Radiobutton(bf, text="Ollama（本機）", variable=self.backend, value="ollama").pack(side="left", padx=6)
        ttk.Radiobutton(bf, text="Claude（需連網）", variable=self.backend, value="claude").pack(side="left")
        self.bools = {}
        for j, (k, label) in enumerate([("auto_stop", "長段口述停頓時自動結束"), ("beep", "開始／結束時嗶一聲"),
                                        ("punctuation", "自動加標點")]):
            v = tk.BooleanVar(value=bool(c[k])); self.bools[k] = v
            ttk.Checkbutton(f2, text=label, variable=v).grid(row=n + 1 + j, column=1, sticky="w")
        ttk.Label(f2, text="熱鍵寫法例：right ctrl、f9、alt+z", foreground="#777").grid(row=n + 4, column=1, sticky="w")
        ttk.Button(f2, text="儲存並套用", command=self.save_settings).grid(row=n + 5, column=1, sticky="e", pady=10)
        f2.columnconfigure(1, weight=1)

        # 名詞表頁
        f3 = ttk.Frame(nb, padding=10); nb.add(f3, text="名詞表")
        ttk.Label(f3, text="一行一個詞；「錯字 => 正確」代表自動替換；# 開頭是註解").pack(anchor="w")
        self.gloss = tk.Text(f3, font=("Microsoft JhengHei UI", 10), undo=True)
        self.gloss.pack(fill="both", expand=True, pady=6)
        ttk.Button(f3, text="儲存並套用", command=self.save_glossary).pack(anchor="e")
        self.load_glossary_text()
        self.update_help()

    def update_help(self):
        c = self.engine.cfg
        self.help_var.set(
            f"按住【{c['hotkey_dictate']}】照講的打　按住【{c['hotkey_rewrite']}】整理成正式文字　"
            f"按住【{c['hotkey_translate']}】翻譯\n按【{c['hotkey_toggle']}】長段口述　"
            f"選取錯字後按【{c['hotkey_glossary']}】說正確寫法→記入名詞表")

    def load_glossary_text(self):
        self.gloss.delete("1.0", "end")
        self.gloss.insert("1.0", GLOSSARY.read_text(encoding="utf-8") if GLOSSARY.exists() else "")

    def save_glossary(self):
        GLOSSARY.write_text(self.gloss.get("1.0", "end").rstrip() + "\n", encoding="utf-8")
        if self.engine.rec:
            self.engine.rec.reload_glossary()
        self.status_var.set("名詞表已儲存並套用")

    def save_settings(self):
        c = self.engine.cfg
        try:
            for k, v in self.vars.items():
                val = v.get().strip()
                c[k] = float(val) if k == "silence_sec" else int(val) if k == "num_beams" else val
        except ValueError:
            self.status_var.set("數字欄位格式不對，未儲存")
            return
        c["llm_backend"] = self.backend.get()
        for k, v in self.bools.items():
            c[k] = v.get()
        save_config(c)
        if self.engine.rec:
            try:
                self.engine.bind_hotkeys()
            except Exception as e:
                self.status_var.set(f"熱鍵設定有誤：{e}")
                return
        self.update_help()
        self.status_var.set("設定已儲存並套用")

    def copy_history(self):
        sel = self.history.curselection()
        if sel:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.items[sel[0]])

    def toggle_pause(self):
        e = self.engine
        e.paused = not e.paused
        self.set_state("paused" if e.paused else "ready", "已暫停（熱鍵不作用）" if e.paused else "待命中")

    def set_state(self, state, msg):
        self.state = state
        self.status_var.set(f"● {STATE_NAMES.get(state, state)}　{msg}")
        self.icon.icon = make_icon(COLORS.get(state, "#9e9e9e"))
        self.icon.title = f"微風語音輸入：{msg or STATE_NAMES.get(state, '')}"[:120]

    def show(self):
        self.root.deiconify(); self.root.lift(); self.root.focus_force()

    def hide(self):
        self.root.withdraw()

    def poll(self):
        try:
            while True:
                m = self.q.get_nowait()
                if m[0] == "status":
                    if not (self.engine.paused and m[1] == "ready"):
                        self.set_state(m[1], m[2])
                elif m[0] == "result":
                    _, mode, text, extra = m
                    line = f"{time.strftime('%H:%M')} [{MODE_NAMES[mode]}] {text}"
                    if extra and mode != "glossary":
                        line += f"　（原話：{extra}）"
                    elif extra:
                        line = f"{time.strftime('%H:%M')} [{MODE_NAMES[mode]}] {extra}"
                        self.load_glossary_text()
                    self.items.insert(0, text)
                    self.history.insert(0, line)
                elif m[0] == "show":
                    self.show()
                elif m[0] == "pause":
                    self.toggle_pause()
                elif m[0] == "quit":
                    self.icon.stop(); self.root.destroy(); os._exit(0)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    import ctypes
    # 避免同時開兩個
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "BreezeVoiceInputApp")
    if ctypes.windll.kernel32.GetLastError() == 183:
        ctypes.windll.user32.MessageBoxW(None, "微風語音輸入已經在執行了，請看工作列右下角的麥克風圖示。", "微風語音輸入", 0)
    else:
        try:
            App().run()
        except Exception:
            log.exception("程式錯誤")
            raise
