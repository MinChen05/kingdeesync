# HyperFrames Bear Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一个基于参考 PNG 的 `9:16`、`15s` 小熊虫草地奔跑短视频，并导出 mp4。

**Architecture:** 在 `video/hyperframes-bear-run/` 中创建独立 HyperFrames 最小工程，使用单场景 HTML + GSAP 驱动角色、影子、草地和云层动画。角色以单图木偶式动画表达奔跑与小跳，最终通过 HyperFrames CLI 渲染成视频。

**Tech Stack:** HTML, CSS, GSAP, HyperFrames CLI, npm/npx

---

### Task 1: 建立工程目录与素材布局

**Files:**
- Create: `video/hyperframes-bear-run/package.json`
- Create: `video/hyperframes-bear-run/index.html`
- Create: `video/hyperframes-bear-run/assets/`

- [ ] **Step 1: 创建最小目录结构**

```bash
mkdir -p video/hyperframes-bear-run/assets
```

- [ ] **Step 2: 放入参考 PNG 作为主角色素材**

```bash
cp /Users/chenjintao/Downloads/image-1778199800437_crops/cells/01_default.png \
  video/hyperframes-bear-run/assets/bear.png
```

- [ ] **Step 3: 写入最小 `package.json`**

```json
{
  "name": "hyperframes-bear-run",
  "private": true
}
```

### Task 2: 编写单场景动画组合

**Files:**
- Modify: `video/hyperframes-bear-run/index.html`

- [ ] **Step 1: 定义 `1080x1920` 根组合和静态布局**
- [ ] **Step 2: 加入天空、云层、远景草地、前景草叶、小花、影子与角色**
- [ ] **Step 3: 用 GSAP 编排 15 秒奔跑与小跳**
- [ ] **Step 4: 输出到 `window.__timelines`**

### Task 3: 安装与渲染

**Files:**
- Output: `video/hyperframes-bear-run/dist/bear-run.mp4`

- [ ] **Step 1: 安装或调用 HyperFrames CLI**

```bash
cd video/hyperframes-bear-run
npx hyperframes@latest lint
```

- [ ] **Step 2: 运行校验**

```bash
cd video/hyperframes-bear-run
npx hyperframes@latest validate
```

- [ ] **Step 3: 渲染视频**

```bash
cd video/hyperframes-bear-run
npx hyperframes@latest render --output dist/bear-run.mp4
```

### Task 4: 验证输出

**Files:**
- Verify: `video/hyperframes-bear-run/dist/bear-run.mp4`

- [ ] **Step 1: 检查文件存在且时长接近 15 秒**

```bash
ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 \
  video/hyperframes-bear-run/dist/bear-run.mp4
```

- [ ] **Step 2: 如有需要导出首帧截图做人工复核**

```bash
ffmpeg -y -i video/hyperframes-bear-run/dist/bear-run.mp4 -vf "select=eq(n\\,0)" -vframes 1 \
  video/hyperframes-bear-run/dist/first-frame.png
```
