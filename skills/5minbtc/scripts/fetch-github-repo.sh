#!/usr/bin/env bash
# fetch-github-repo.sh — 受限网络下下载GitHub仓库的通用脚本
#
# 用法: ./fetch-github-repo.sh <owner/repo> [output_dir] [branch]
# 示例: ./fetch-github-repo.sh ZhuLinsen/daily_stock_analysis ./repos/daily_stock_analysis main
#
# 背景:
#   在中国大陆网络下，git clone / gh repo clone / codeload.zip 经常因TLS握手超时失败
#   (典型错误: GnuTLS recv error (-110), Operation timed out, unexpected EOF)
#   本脚本绕过git协议，走 api.github.com tarball端点，断点续传+多重重试
#
# 注意:
#   - 不需要GitHub auth (匿名tarball支持)
#   - 不需要git客户端
#   - 适合单仓库下载，不需要commit历史
#   - 默认下载 tarball，但若仅需几个文件见fetch-github-files.sh

set -e

REPO="${1:?Usage: $0 owner/repo [output_dir] [branch]}"
OUTDIR="${2:-$(basename "$REPO")}"
BRANCH="${3:-main}"

# 规范化 output dir 为绝对路径
mkdir -p "$OUTDIR"
OUTDIR="$(cd "$OUTDIR" && pwd)"

TARBALL="/tmp/github-$(echo "$REPO" | tr '/' '-').tgz"
WORKDIR="$(mktemp -d)"

echo "==> 下载 $REPO @ $BRANCH → $TARBALL"

# wget -c 断点续传，--tries=30 长重试链，120s单次超时适合慢网
wget --tries=30 --timeout=120 --read-timeout=120 -c \
  -O "$TARBALL" \
  "https://api.github.com/repos/$REPO/tarball/$BRANCH" 2>&1 | tail -8

# 完整性校验
SIZE=$(stat -c%s "$TARBALL")
echo "==> 下载完成: $SIZE bytes"
echo "==> 验证tarball完整性..."

if ! tar -tzf "$TARBALL" >/dev/null 2>&1; then
  echo "⚠️  tarball不完整（EOF截断），但可能部分文件仍可解压" >&2
fi

# 列出文件数
FILE_COUNT=$(tar -tzf "$TARBALL" 2>/dev/null | wc -l)
echo "==> tarball内文件数: $FILE_COUNT"

# 解压
cd "$WORKDIR"
tar -xzf "$TARBALL"

# GitHub tarball 解压到 "{owner}-{repo}-{sha}/" 目录
SRC_DIR=$(find . -maxdepth 1 -type d -not -name '.' | head -1)
if [ -z "$SRC_DIR" ]; then
  echo "❌ 解压后未找到源码目录" >&2
  exit 1
fi

# 移动到目标位置
if [ -d "$OUTDIR" ] && [ "$(ls -A "$OUTDIR" 2>/dev/null)" ]; then
  echo "==> 目标目录已存在非空，合并内容到 $OUTDIR"
  cp -r "$SRC_DIR"/. "$OUTDIR"/
else
  rm -rf "$OUTDIR"
  mv "$SRC_DIR" "$OUTDIR"
fi

# 清理
rm -rf "$WORKDIR"

echo ""
echo "✅ 完成: $REPO → $OUTDIR"
echo "   解压后文件数: $(find "$OUTDIR" -type f | wc -l)"
echo "   占用空间: $(du -sh "$OUTDIR" | cut -f1)"