# 各平台详细参考信息

## 百家号 (Baijiahao)

### URL信息
- **首页**: https://baijiahao.baidu.com/
- **发布页面**: https://baijiahao.baidu.com/builder/rc/edit?type=news
- **发布图文**: https://baijiahao.baidu.com/builder/rc/edit?type=news
- **发布视频**: https://baijiahao.baidu.com/builder/rc/edit?type=video
- **登录页面**: https://baijiahao.baidu.com/

### 登录状态检测特征
页面中存在以下元素表示已登录：
- `头像` (image元素)
- `发布作品`
- `内容管理`
- `作品管理`

### 发布按钮定位
- 主按钮：`发布作品` (StaticText)
- 图文选项：`发布图文` (StaticText)
- 视频选项：`发布视频` (StaticText)

### 常见弹窗及处理
| 弹窗类型 | 关闭按钮特征 |
|----------|--------------|
| 活动推广 | `关闭`、`×`、`不再提示` |
| 升级提示 | `暂不升级`、`以后再说` |
| 会员广告 | `关闭`、`跳过` |

---

## 搜狐号 (Sohu MP)

### URL信息
- **首页**: https://mp.sohu.com/
- **发布页面**: https://mp.sohu.com/api/author/article/new
- **登录页面**: https://mp.sohu.com/

### 登录状态检测特征
- `发布文章`
- `内容管理`
- `个人中心`

### 发布按钮定位
- `发布文章`
- `写文章`

---

## 知乎 (Zhihu)

### URL信息
- **首页**: https://www.zhihu.com/
- **专栏发布页**: https://zhuanlan.zhihu.com/write
- **登录页面**: https://www.zhihu.com/signin

### 登录状态检测特征
- `写文章`
- `首页`
- `通知`
- `私信`

### 发布按钮定位
- `写文章`
- `发布`

---

## 弹窗关闭策略

### 通用弹窗特征

**关闭按钮文本模式（中文）：**
```
关闭, ×, ✕, 我知道了, 知道了, 不再提示, 不再显示, 跳过,
以后再说, 暂不, 取消, 不升级, 稍后, 关闭此
```

**关闭按钮文本模式（英文）：**
```
close, ×, ✕, got it, skip, not now, later, cancel, dismiss, hide
```

**弹窗容器关键词：**
```
广告, 弹窗, 弹框, 浮层, 蒙层, 遮罩, dialog, modal, popup,
overlay, banner, ad, advertisement
```

### 关闭流程

1. 获取页面快照
2. 分析快照文本，匹配弹窗特征
3. 查找关闭按钮uid（格式：`uid=xxx`）
4. 执行点击操作
5. 重新获取快照确认关闭

---

## 快照分析技巧

### 解析快照中的uid

快照文本格式示例：
```
uid=1_10 button "关闭"
uid=1_11 dialog "广告推广"
```

提取uid的正则表达式：`uid=([0-9]+_[0-9]+)`

### 判断元素类型

- `button` - 可点击的按钮
- `link` - 链接
- `dialog` - 对话框
- `textbox` - 输入框

### 优先点击顺序

1. 专门的关闭按钮（role=button 且text包含关闭关键词）
2. 弹窗容器内的关闭元素
3. 带有 × 符号的元素
