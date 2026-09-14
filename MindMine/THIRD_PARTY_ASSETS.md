# 第三方素材来源

本文件记录 MindMine 使用的所有第三方素材及其授权信息。
即使授权本身不强制署名，也在此保留来源记录，便于后续复核与替换。

---

## 音频

### 背景音乐（全局唯一一首）

```
Track:       What it Takes
Artist:      Eugenio Mininni
Source:      https://mixkit.co/free-stock-music/ambient/
Direct URL:  https://assets.mixkit.co/music/616/616.mp3
License:     Mixkit Stock Music Free License
License URL: https://mixkit.co/license/#musicFree
Genre:       Ambient
Published:   2020-01-28
Downloaded:  2026-09-14
Local path:  frontend/public/audio/mindmine-ambient.mp3
```

**授权要点**（依据 Mixkit Stock Music Free License）

- 可免费用于商业与非商业项目，无需署名。
- 允许在网站、社交平台、演示与视频中使用。
- 不得以素材库、模板或源文件形式再分发，不得声明为自有作品，
  不得在任何版权管理服务上注册。

MindMine 的用法是「网页内嵌背景音乐」，属于授权范围内的最终产品使用，
不涉及再分发。

**本地处理**（不改变授权性质，仅为适配 Web 播放）

原始文件 4:58 / 9.09 MB / 44.1kHz 立体声，经以下处理后入库：

| 处理 | 原因 |
| --- | --- |
| 裁掉首尾静音（3.9s / 3.9s） | 原曲开头近 4 秒接近无声，用户点开会误以为没播放 |
| 首尾各 1.5s 交叉淡化 | 让 `loop` 接缝听不出断点 |
| 立体声 → 单声道，44.1k → 32kHz | BGM 在 0.18 音量下听感无差别，体积从 9.09 MB 降到 1.12 MB |
| 峰值归一化到 0.89 | 留足余量，避免浏览器端叠加增益时削波 |

处理后：4:50（290.4s）/ 1.12 MB / 32kHz 单声道。

**选它的原因**

在 Option A（Ambient / Reflective）、Option B（Warm Lo-fi）、
Option C（Minimal Electronic）三个方向共下载 5 首候选，
做客观音频分析后选定。关键指标如下（越低越适合当背景）：

| 候选 | 1–4kHz 人声频段占比 | 低频隆隆 | 动态范围 | 结论 |
| --- | --- | --- | --- | --- |
| Forest Mist Whispers | 10.9% | 24.1% | 36.0 dB | 起伏过大，会抢注意力 |
| Rest Now | 23.8% | 5.5% | 26.2 dB | 直接压住人声，Demo 讲解会被盖 |
| Sonor #2 | 5.6% | 22.2% | 21.5 dB | 首尾电平差 205 dB，无法循环 |
| Opalescent | 3.0% | 24.1% | 30.9 dB | 低频偏重，笔记本外放发糊 |
| **What it Takes** | **3.3%** | **0.0%** | **24.3 dB** | **入选** |

`What it Takes` 同时满足三个硬条件：几乎不占用人声频段（现场讲解不被干扰）、
无低频隆隆（笔记本外放清晰）、动态最平稳（不会突然变响把人拽出思考）。

需要说明：最初按标签最看好的 `Forest Mist Whispers`，
在实测中因 36 dB 动态范围被否决 —— 标签描述与实际听感并不一致。

---

## 其他

当前无其他第三方素材。新增时请按上述格式补充：

```
Track / Asset:
Artist / Author:
Source:
License:
Downloaded:
```
