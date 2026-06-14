# Patches

這個資料夾保存對上游專案的本地 patch。

- `open-llm-vtuber.patch`: 本地播報 API 與音訊轉檔修補
- `hung-yi-lee-skill.patch`: Python 3.9 / UTF-8 / graph loading 相容性修補

套用方式：

```powershell
git apply .\patches\open-llm-vtuber.patch
git apply .\patches\hung-yi-lee-skill.patch
```
