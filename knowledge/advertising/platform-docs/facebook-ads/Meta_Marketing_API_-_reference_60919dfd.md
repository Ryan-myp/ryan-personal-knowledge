# Meta Marketing API - reference

> **来源**: Meta Marketing API
> **更新时间**: 2026-08-14
> **版本**: latest
> **类型**: api-reference/documentation
> **标签**: facebook-ads, api, documentation

## 📌 概述

来自 Meta Marketing API 官方文档

---

市场营销 API 参考文档 更新时间 : 2026年6月26日 为 LLM 复制 作为 Markdown 查看 WhatsApp 动态广告可通过市场营销 API 获取。 详细了解 WhatsApp 动态中的广告。 营销 API 根节点 本文将提供 Facebook 市场营销 API 的完整根节点列表，并附有各个根节点的参考文档链接。有关API架构的背景以及如何调用根节点及其边缘,请参见 使用图形API 。 您需要登录 Facebook 才能访问所有参考文档信息。 节点 描述 /{AD_ACCOUNT_USER_ID} 创建广告的 Facebook 用户。每个广告用户可拥有多个广告帐户下的身份。 /act_{AD_ACCOUNT_ID} 表示管理广告的商家实体。 /{AD_ID} 包含广告信息，如创意元素和成效衡量信息。 /{AD_CREATIVE_ID} 图片、轮播、精品栏或视频广告的格式。 /{AD_SET_ID} 包含使用同一预算、排期、竞价和定位数据的所有广告。 /{AD_CAMPAIGN_ID} 定义你的广告目标。包含一个或多个广告组。 用户 用户连线 连线 描述 /adaccounts 与此用户关联的所有广告帐户 /accounts 某用户管理的所有公共主页和地点 /promotable_events 您创建的所有可推广活动，或您担任管理员的公共主页中的可推广公共主页活动 广告帐户 营销 API 中的所有广告对象集合属于 ad account 。 广告账户连线 广告帐户节点最常用的连线。访问 广告帐户边缘参考 获取所有边缘的完整列表。 连线 描述 /adcreatives 定义广告的外观和内容 /adimages 在广告创意中使用的图片库。独立于广告创意上传和管理这些图片 /ads 广告数据，如创意元素和成效衡量信息 /adsets 包含使用同一预算、排期、竞价和定位数据的所有广告 /advideos 在广告创意中使用的视频库。上传和管理这些视频,独立于广告创意 /campaigns 定义广告系列的目标并包含一个或多个广告组 /customaudiences 此广告帐户拥有的自定义受众/与之共享的自定义受众 /insights 成效分析界面。删除子对象的重复结果，提供整理好的异步报告。 /users 与广告帐户关联的人员名单 广告 与广告组关联的单个广告。 广告连线 广告节点最常用的连线。访问 Ad Edges参考 获取所有边缘的完整列表。 连线 描述 /adcreatives 定义广告的外观和内容 /insights 广告表现的成效分析。 /leads 与潜客广告相关的任何潜客信息。 /previews 通过现有广告生成广告预览 广告组 广告组是一组共享相同单日预算或总预算、排期、竞价类型、竞价信息和定位数据的广告。 广告组连线 广告组节点最常用的连线。访问 广告组边缘参考 获取所有边缘的完整列表。 连线 描述 /activities 对广告组的操作日志 /adcreatives 定义你的广告内容和外观 /ads 广告的必要数据，如创意元素和成效衡量信息 /insights 广告表现的成效分析。 广告活动 广告系列是广告账户中最高级别的组织结构，代表广告主的单个目标。 广告系列连线 广告系列节点最常用的连线。访问 广告营销边缘参考 获取所有边缘的完整列表。 连线 描述 /ads 广告的必要数据，如创意元素和成效衡量信息 /adsets 包含使用同一预算、排期、竞价和定位数据的所有广告。 /insights 广告表现的成效分析。 广告创意 用于提供布局并包含广告内容的格式。 广告创意连线 广告创意节点最常用的连线。访问 广告创意边缘参考 获取所有边缘的完整列表。 连线 描述 /previews 通过现有的广告创意对象生成广告预览

---

## 📚 参考资料

- **原始文档**: https://developers.facebook.com/docs/marketing-api/reference
- **获取时间**: 2026-08-14T20:37:04.521758
- **版本**: latest

## 🔗 相关链接

- [TikTok Ads API 门户](https://business-api.tiktok.com/portal)
- [Meta Marketing API](https://developers.facebook.com/docs/marketing-api)
- [Google Ads API](https://developers.google.com/google-ads/api)
- [Display & Video 360 API](https://developers.google.com/display-video/api)
