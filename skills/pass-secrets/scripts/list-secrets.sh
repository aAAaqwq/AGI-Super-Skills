#!/bin/bash
# 列出所有存储的密钥（脱敏显示）
# 用法: ./list-secrets.sh

echo "========================================="
echo "  Pass 密钥库"
echo "========================================="
echo ""

pass ls

echo ""
echo "========================================="
echo "  密钥预览（脱敏）"
echo "========================================="
echo ""

# 遍历所有密钥
list_secrets() {
    local dir=$1
    local prefix=$2
    
    for file in "$dir"/*.gpg 2>/dev/null; do
        if [ -f "$file" ]; then
            local name=$(basename "$file" .gpg)
            local path="${prefix}${name}"
            local value=$(pass "$path" 2>/dev/null)
            if [ -n "$value" ]; then
                local preview="${value:0:10}...${value: -6}"
                printf "%-30s %s\n" "$path:" "$preview"
            fi
        fi
    done
    
    # 递归子目录
    for subdir in "$dir"/*/; do
        if [ -d "$subdir" ]; then
            local subname=$(basename "$subdir")
            list_secrets "$subdir" "${prefix}${subname}/"
        fi
    done
}

list_secrets "$HOME/.password-store" ""

echo ""
echo "========================================="
echo "  使用方法"
echo "========================================="
echo ""
echo "查看完整密钥:  pass <路径>"
echo "复制到剪贴板:  pass -c <路径>"
echo "添加新密钥:    pass insert <路径>"
echo "编辑密钥:      pass edit <路径>"
echo ""
