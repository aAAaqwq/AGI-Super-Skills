# Domain whitelist → force MinerU

When `source_url` matches any domain in this list (exact host match or subdomain), **skip probe** and go directly to **MinerU-HTML**.

Rationale: these sites frequently block automated fetches, render dynamically, or return interstitial/captcha pages.

## Default whitelist

- mp.weixin.qq.com
- mmbiz.qpic.cn (WeChat images; usually appears as assets)
- zhuanlan.zhihu.com
- www.zhihu.com
- zhihu.com
- xhslink.com
- xiaohongshu.com

## Notes

- Matching rule: `host == domain` OR `host.endswith('.' + domain)`
- You can add/remove domains here based on real failures.
