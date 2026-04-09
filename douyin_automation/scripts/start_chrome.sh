#!/bin/bash
# 启动 Chrome 调试模式 + 自动采集脚本
# 用法：bash scripts/start_chrome.sh [--top N] [--category 类目]
#
# 流程：
#   1. 启动 Chrome（调试端口 9222）
#   2. 等待你手动登录飞瓜和抖音
#   3. 确认后自动运行采集脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
USER_DATA_DIR="$HOME/.chrome-douyin-automation"

# 透传参数给采集脚本
COLLECT_ARGS="$@"

# 如果找不到 Chrome，尝试 Chromium
if [ ! -f "$CHROME_PATH" ]; then
    CHROME_PATH="/Applications/Chromium.app/Contents/MacOS/Chromium"
fi

if [ ! -f "$CHROME_PATH" ]; then
    echo "❌ 未找到 Chrome 或 Chromium，请确认安装路径"
    exit 1
fi

# ── Step 1: 启动 Chrome ───────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║       抖音带货自动化 - 启动 & 采集                   ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "🚀 [1/3] 启动 Chrome 调试模式（端口 9222）..."

# 检查 9222 端口是否已被占用（Chrome 已在运行）
if curl -s http://localhost:9222/json/version > /dev/null 2>&1; then
    echo "     ✅ Chrome 调试端口已在运行，跳过启动"
else
    "$CHROME_PATH" \
        --remote-debugging-port=9222 \
        --user-data-dir="$USER_DATA_DIR" \
        --no-first-run \
        --no-default-browser-check \
        --disable-background-networking \
        "https://dy.feigua.cn" > /dev/null 2>&1 &

    CHROME_PID=$!
    echo "     Chrome PID: $CHROME_PID"

    # 等待 Chrome 启动并监听端口
    echo "     等待 Chrome 就绪..."
    for i in $(seq 1 15); do
        if curl -s http://localhost:9222/json/version > /dev/null 2>&1; then
            echo "     ✅ Chrome 已就绪"
            break
        fi
        sleep 1
        if [ $i -eq 15 ]; then
            echo "     ❌ Chrome 启动超时，请手动检查"
            exit 1
        fi
    done
fi

# ── Step 2: 等待用户登录 ──────────────────────────────────────────────────────

echo ""
echo "🔐 [2/3] 请在 Chrome 中完成登录："
echo "     → 飞瓜数据: https://dy.feigua.cn"
echo "     → 抖音:     https://www.douyin.com"
echo ""
echo "     登录完成后，按 Enter 开始采集..."
read -r

# ── Step 3: 运行采集脚本 ──────────────────────────────────────────────────────

echo ""
echo "📦 [3/3] 开始采集素材..."
echo ""

cd "$PROJECT_DIR"
python3 scripts/collect_real_materials.py $COLLECT_ARGS
