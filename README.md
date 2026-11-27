<div align="center">

<img src="assets/icon.png" width="128" alt="微風語音輸入圖示">

# 微風語音輸入 Breeze Voice Input

**Windows 本機語音輸入：按住熱鍵說話，放開就打進任何程式（LINE、瀏覽器、Word…）。**
**用聯發科 Breeze-ASR-25 辨識台灣華語與中英夾雜，全程在你自己的電腦上執行。**

[English summary](#english-summary)

</div>

---

## 為什麼做這個

Windows 內建語音輸入（Win+H）、手機鍵盤、ChatGPT 語音，在台灣華語、專有名詞、中英夾雜時常常聽錯，有時還會「幻覺」出沒講過的句子（例如「謝謝收看」「請訂閱」）。

這個工具把幾件事組在一起，讓 Windows 上的語音打字更準、更好用：

- **台灣華語模型**：[Breeze-ASR-25](https://huggingface.co/MediaTek-Research/Breeze-ASR-25)（以 Whisper large-v2 為基礎、針對台灣華語與中英夾雜調整）
- **自動標點**：Breeze 的輸出沒有標點，另用 FunASR 的 CT-Transformer 標點模型在本機補上
- **防幻覺**：太短或太小聲的錄音直接略過、刪除常見的幻覺句、去掉重複片語
- **名詞表**：自己的專有名詞和常錯字，辨識時提示模型，辨識後自動更正

## 功能

| 按法（可在設定中修改） | 功能 |
|---|---|
| 按住 **右 Ctrl** 說話 | 照你說的打出來（繁體、有標點） |
| 按住 **F9** 說話 | 由 AI 整理成通順的書面語再打出來 |
| 按住 **F7** 說話 | 說中文，打出翻譯（預設英文） |
| 按一下 **F8** | 長段口述；停頓幾秒自動結束 |
| 先**選取打錯的字**，按 **F10** 說出正確的詞 | 直接改掉錯字，並記進名詞表，下次自動更正 |

- **工作列圖示**：右下角小圓點顯示狀態（灰＝載入中、綠＝待命、紅＝錄音中、橘＝處理中、藍＝暫停）。雙擊開視窗，關閉視窗只會縮回工作列。
- **設定視窗**：熱鍵、自動停止秒數、整理風格、翻譯語言、AI 來源、嗶聲、標點、辨識精細度，都能調整；名詞表可直接編輯；提示音預設關閉，可在設定中開啟。
- **外觀**：蘋果科技風、日系和紙、陶土工作室三款可即時切換。主視窗和浮動錄音列會一起換色，程式會記住選擇。
- **浮動錄音列**：按住右 Ctrl 時顯示音量與狀態，不搶正在輸入的視窗焦點。短按略過，錄音中按 Esc 取消。
- **本次文字**：辨識完成後可在主視窗編輯或複製。如果切換了視窗，微風會保留文字供手動貼上。程式只保留最近一筆於記憶體，沒有歷史檔。
- **錄音不會存檔**：聲音只暫存在記憶體，辨識完就丟掉。

## 系統需求

- Windows 10 / 11
- **NVIDIA 顯示卡**（建議 8GB 以上顯示記憶體；作者用 RTX 5060 Ti 16GB 測試）
- Python 3.10～3.12
- 約 4GB 磁碟空間（辨識模型第一次啟動時自動下載）
- F9 整理／F7 翻譯另需本機 AI（擇一）：[Ollama](https://ollama.com/) 或 [LM Studio](https://lmstudio.ai/)；或已登入的 [Claude Code](https://claude.com/claude-code) 命令列

## 安裝

1. 下載本專案（綠色 **Code** 按鈕 → Download ZIP），解壓縮到簡單的路徑，例如 `D:\BreezeVoiceInput`
2. 在資料夾裡按右鍵「在終端機中開啟」，執行：
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```
   想要開機自動啟動，改執行：
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Startup
   ```
3. 雙擊桌面「**微風語音輸入**」。第一次會下載模型，之後約 30 秒載入完成，聽到「嗶」一聲就能用。

### 啟用 F9 整理／F7 翻譯（選用）

- **Ollama（預設）**：安裝 Ollama 後執行 `ollama pull qwen3:8b`
- **LM Studio**：在設定視窗選「LM Studio」並填入模型名稱。LM Studio 沒開時，程式會用 `lms` 命令列在背景啟動伺服器並載入模型
- **Claude**：在設定視窗選「Claude」。這個選項會把文字送到雲端，其他功能都在本機

## 使用小提醒

- F9 整理過的文字請**看過再送出**：已限制 AI 不得新增你沒說的事實，但它仍可能改變原意
- 以系統管理員身分執行的程式，可能收不到熱鍵（Windows 的限制）
- 設定、名詞表、紀錄檔放在 `%LOCALAPPDATA%\BreezeVoiceInput`
- 解除安裝：刪除本資料夾、桌面與「啟動」資料夾裡的捷徑，以及 `%LOCALAPPDATA%\BreezeVoiceInput`

## 致謝與參考

**使用的模型與套件**

| 項目 | 用途 | 授權 |
|---|---|---|
| [MediaTek Research / Breeze-ASR-25](https://huggingface.co/MediaTek-Research/Breeze-ASR-25) | 台灣華語語音辨識 | Apache-2.0 |
| [FunASR / ct-punc](https://huggingface.co/funasr/ct-punc)（[FunASR](https://github.com/modelscope/FunASR)） | 中文標點還原、靜音偵測框架 | Apache-2.0 |
| [Hugging Face Transformers](https://github.com/huggingface/transformers)、[PyTorch](https://pytorch.org/) | 模型執行 | Apache-2.0 / BSD |
| [OpenCC](https://github.com/yichen0831/opencc-python) | 簡繁轉換 | Apache-2.0 |
| [keyboard](https://github.com/boppreh/keyboard)、[pystray](https://github.com/moses-palmer/pystray)、[sounddevice](https://github.com/spatialaudio/python-sounddevice)、[pyperclip](https://github.com/asweigart/pyperclip)、[Pillow](https://github.com/python-pillow/Pillow) | 熱鍵、工作列、錄音、剪貼簿、圖示 | MIT / LGPL / MIT / BSD / MIT-CMU |

**參考了這些專案的功能設計**（以下專案的程式碼都沒有直接使用，只是參考它們的做法，在此致謝）

- [chenlu-hung/BreezeTyping](https://github.com/chenlu-hung/BreezeTyping)：macOS 上「Breeze-ASR-25 ＋ CT-Transformer 標點 ＋ LLM 校正」的做法，是本工具辨識流程的主要參考
- [SanHsien/voxprose（聲成文）](https://github.com/SanHsien/voxprose)：Windows 語音輸入、AI 潤飾與翻譯、詞彙記憶。**如果你需要更完整的功能（雲端辨識、情境風格、安裝包），推薦使用 VoxProse**
- [savbell/whisper-writer](https://github.com/savbell/whisper-writer)：熱鍵聽寫、靜音自動停止
- [rock74710/TypelessMLX](https://github.com/rock74710/TypelessMLX)：Breeze-ASR-25 聽寫、語助詞過濾、聽寫歷史
- [gary0413/SayKey](https://github.com/gary0413/SayKey)：術語修正
- [ChrisChoTW/remote-voice-input](https://github.com/ChrisChoTW/remote-voice-input)：工作列狀態圖示

本工具的差異在於：**Windows ＋ Breeze-ASR-25** 的組合、選取錯字後直接用說的修正並記進名詞表，以及可沿用 LM Studio／Ollama 裡現有的本機模型。

本專案在 AI 程式助理（Claude Code）協助下完成。

## 授權

[MIT License](LICENSE)。使用的模型與套件依各自的授權條款。

---

## English summary

**Breeze Voice Input** is a local push-to-talk dictation tool for Windows. Hold a hotkey, speak, release — the text is typed into whichever app has focus. It uses MediaTek's [Breeze-ASR-25](https://huggingface.co/MediaTek-Research/Breeze-ASR-25) (Taiwanese Mandarin & Mandarin-English code-switching), FunASR CT-Transformer punctuation, hallucination filtering and a personal glossary. Optional hotkeys rewrite speech into formal text or translate it, using a local LLM (Ollama / LM Studio) or the Claude CLI. Requires an NVIDIA GPU. Audio is never saved. Inspired by BreezeTyping, VoxProse, whisper-writer, TypelessMLX, SayKey and remote-voice-input (no code copied). MIT licensed.
