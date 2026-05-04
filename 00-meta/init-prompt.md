# GEO Engine 初始化引导 Prompt

> 用途：当用户说"初始化系统"或 brand.csv 为占位符时，引导用户完成 3 步配置。

---

## 第 1 步：选择目标市场

```
请选择目标市场：
  [1] 国内 GEO（中文，面向中国大陆市场）
      → 目标 AI 平台：豆包、DeepSeek、通义千问、Kimi
      → 关键词语言：中文
  [2] 国外 GEO（英文/多语言，面向海外市场）
      → 目标 AI 平台：ChatGPT、Perplexity、Gemini、Claude
      → 关键词语言：英文
  [3] 双市场（同时覆盖国内和国外）
      → 生成中英文两套关键词和内容
```

## 第 2 步：填写品牌基础信息

```
请提供以下品牌信息（可逐项填写，也可一次性提供）：

品牌/公司名称：
行业/品类：
核心产品/服务（1-2句话）：
目标客户/ICP画像：
独特优势/价值主张：
官网地址：
竞品列表（用分号分隔，如 竞品A;竞品B;竞品C）：
目标 AI 平台（用逗号分隔，如 doubao,deepseek,chatgpt）：
内容语言（zh 或 en）：
```

## 第 3 步：确认并保存

```
请确认以上信息是否正确？
  [Y] 确认，写入 brand.csv 并进入关键词生成
  [N] 重新填写
```

确认后将信息写入 `data/brand.csv`，格式为键值对（field,value）：

```csv
field,value
brand_name,填写的品牌名
industry,填写的行业
product_description,填写的产品描述
target_customer,填写的ICP
core_value_prop,填写的价值主张
website_url,填写的官网URL
competitors,竞品A;竞品B;竞品C
geo_target_platforms,"doubao,deepseek,chatgpt"
language,zh
market,domestic
```
