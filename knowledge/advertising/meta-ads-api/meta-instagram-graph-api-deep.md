# Instagram Graph API 深度解析（Business Account / 内容 / 洞察 专项）

> **领域**: 广告投放 / Meta
> **深度**: ⭐⭐⭐⭐⭐ API 专项指南
> **标签**: meta-ads-api, instagram, graph-api, ig-business, insights, hashtags
> **更新时间**: 2026-08-14
> **类型**: api-guide/deep

---

## 目录速览

本文是 **Instagram Graph API（IG Graph API）专项深度文档**，与同目录下的 `meta-marketing-api-deep.md`（Meta Marketing API 通用：广告系列 / 广告组 / 广告 / Pixel / CAPI）互补。后者讲"**用广告投放 Instagram**"，本文讲"**通过 API 直接操作 Instagram 商业账号的原生内容与数据**"：发帖、评论互动、话题标签、账号与媒体洞察、以及 Webhooks 实时订阅。

> 一句话定位两者边界：**Marketing API 驱动"买量投放"，Instagram Graph API 驱动"原生经营"**。对于品牌自营账号（Owned Account）、网红 UGC 治理、评论区客服、话题趋势监控等场景，主角都是 Instagram Graph API。

全文按统一的五大板块组织：

| 板块 | 内容 | 阅读优先级 |
|------|------|-----------|
| 一、核心概念与架构 | IG Business Account 绑定、权限体系、标识符、对象模型、总架构图 | 必读 |
| 二、深度原理解析 | 认证、/me/accounts、内容创建与发布时序、评论、Hashtag、Insights、Webhooks、公开 vs 私有 | 重点 |
| 三、生产环境实战 | 封装 `meta_*` 工具函数、批量发布、限流与重试、Webhooks 落地 | 重点 |
| 四、常见问题与排查 | 错误码矩阵、发布被拒、权限不足、数据延迟、限流、绑定异常 | 排查手册 |
| 五、自测题 | 4 道深入问题与答案 | 巩固 |

---

## 一、核心概念与架构

### 1.1 Instagram Graph API 是什么

Instagram Graph API 是 Meta 面向**Instagram 商业账号 / 创作者账号（Instagram Business / Creator Account）**开放的官方 REST API（Graph API 的一个子集）。它允许第三方应用：

- 读取 / 创建 / 发布 Instagram 原生媒体的容器与帖子；
- 读写媒体评论、回复、@提及；
- 搜索并聚合 Hashtag（话题标签）的公开内容；
- 读取账号级与媒体级 Insights（reach、impressions、profile_views、follower_count、video_views、saved、engagement 等）；
- 管理关注关系（follow / unfollow）；
- 订阅实时事件（Webhook：`comments`、`mentions` 等）。

**核心约束（第一课）：** Instagram Graph API **只能操作"Instagram 商业账号 / 创作者账号"**。个人号（Personal Account）既不提供 `instagram_business_account` 绑定，也不开放任何 `insights`、`media` 发布端点。这是与 Marketing API 最大的差异之一：**你无法对任意 Instagram 个人号用 API 发帖或读数据**。

#### 1.1.1 与 Marketing API 的边界对照

| 维度 | Meta Marketing API | Instagram Graph API |
|------|-------------------|---------------------|
| 操作对象 | 广告账户 act_xxx、Campaign/AdSet/Ad、Pixel、受众 | IG 商业账号 IGID、Media、Comment、Hashtag、Insights |
| 目的 | 付费投放、买量、归因、转化 | 原生发帖、社媒运营、UGC 监管、数据洞察 |
| 账号前提 | Facebook 广告账户 + BM | **Instagram 商业/创作者账号绑定 FB Page** |
| 令牌 | 系统用户 / 广告用户 token | **用户访问令牌 + Page 关联 + 应用权限** |
| 典型用途 | 广告投放报告、受众再营销 | 评论区客服、话题监控、内容日历自动发帖 |
| 关系 | 可投放 Instagram 版位广告（走 Marketing API） | 读取 IG 原生互动数据供投放参考 |

#### 1.1.2 Instagram Graph API 在 Meta 产品栈中的位置

```
                    Meta 开发者产品地图
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│   Marketing API          Instagram Graph API     Messenger     │
│   ┌──────────────┐      ┌──────────────────┐    ┌───────────┐  │
│   │ Campaigns    │      │ Media 发布       │    │ Bot       │  │
│   │ AdSets/Ads   │      │ Comments 互动    │    │ Messaging │  │
│   │ Pixel/CAPI   │      │ Hashtag 聚合     │    └───────────┘  │
│   │ Audiences    │      │ Insights 洞察    │                   │
│   └──────────────┘      └──────────────────┘                   │
│            │                     │                             │
│            └───────────┬─────────┘                             │
│                        ▼                                       │
│          ┌─────────────────────────────┐                       │
│          │   Graph API 统一网关        │                       │
│          │   https://graph.facebook.com│                       │
│          │   /v18.0|v19.0|v20.0|...    │                       │
│          └─────────────────────────────┘                       │
│            前提：App + Instagram 商业账号 + Page 绑定 + 权限    │
└────────────────────────────────────────────────────────────────┘
```

> 关键认知：Instagram Graph API **不是独立域名**，它复用了 Facebook 的 `graph.facebook.com` 网关与 OAuth 体系。这意味着：Page 绑定、App 审核、`access_token`、Webhook 签名等基础设施与 Facebook Graph API 完全同源——**绝大多数"没权限"报错，根源都在 Page/App/账号绑定层**，而非 Instagram 数据层。

### 1.2 核心标识符体系

Instagram Graph API 的关键是分清三类 id。绝大多数新手踩坑，都是把 **IG 用户 ID** 和 **Page ID**、**Instagram 公开数字 ID（IGDBID）** 搞混。

| 标识符 | 示例形态 | 含义与来源 |
|--------|----------|-----------|
| `ig-user-id`（IGID） | `17841400000000000` | **Instagram 商业账号在 Graph API 中的 ID**，是本文几乎所有端点的 `{ig-user-id}`。来自 `GET /{page-id}?fields=instagram_business_account` 或 `/me/accounts` 展开字段 |
| `page-id` | `102290129340398` | Facebook 粉丝页 Page ID，IG 商业账号必须挂接在某个 Page 下 |
| 媒体 id（media-id / container-id） | `17920786867118320` | 已发布媒体或未发布的容器（container）ID，来自 POST 返回值 |
| 评论 id（comment-id） | `17873440459141069` | 评论/回复的 id，用于回复、隐藏、删除、@提及 |
| `ig-hashtag-id` | `17843812461040521` | 通过 hashtag search 得到的数字话题 id，用于 top_media / recent_media 聚合 |
| 应用 id / app-id | `1234567890` | 开发者应用 App ID |
| Instagram 公开 ID（IGDBID） | `salman_hashtag`（账号名） | 账号用户名 ≠ Graph id，`.json` 爬取用的公开数字 id 与 IGID **也不同**，不可混用 |

#### 1.2.1 标识符之间如何换算（一张图）

```
            Facebook 用户（App 管理员/开发者）
                        │ 授权（登录）
                        ▼
       ┌────────────────────────────┐
       │  Facebook Page（粉丝页）    │  ←— 必选项：IG 商业账号必须绑定 Page
       │  id = page-id              │
       │  fields=instagram_business_account ──► ig-user-id (IGID)
       └────────────────────────────┘
                        │ 挂接
                        ▼
       ┌────────────────────────────┐
       │  Instagram 商业账号 / 创作者│
       │  id = ig-user-id (IGID)    │ ←— 唯一可用于 API 的"账号 id"
       └────────────────────────────┘
                        │ 持有
                        ▼
   ┌─────────┬────────────┬──────────────┬──────────────┐
   │ Media   │ Comment    │ Hashtag(id)  │ Follower     │
   │ (容器)  │ (评论/回复) │ 聚合 top/recent│ 关注/取关     │
   └─────────┴────────────┴──────────────┴──────────────┘
```

**一句话记忆：** 所有 API 调用都围绕一个 `ig-user-id` 展开；而拿到它，**必须先有一个绑定到 IG 商业账号的 Facebook Page**，并用一个有相应权限的 `access_token` 去问 Page。

### 1.3 IG 商业账号与 Page 的绑定关系

Instagram **商业账号 / 创作者账号**必须从 Facebook 绑定到一个粉丝页（Page）。绑定关系决定了：

1. **谁能管理**——只有 Page 的管理员（admin）相关权限者，才能代表该 IG 商业账号调用 API；
2. **token 从哪来**——IG Graph API 用**用户令牌（User Access Token）**，且该用户必须是绑定 Page 的管理员；也可用 System User Token；
3. **权限从哪来**——`instagram_basic` 等应用权限 + `pages_read_engagement` / `pages_manage_meta` 等 Page 权限；
4. **Webhook 挂哪**——IG Webhook 订阅挂在 **App** 上，由该 App 绑定管理这些 Page/IG 账号。

```
        绑定关系全景
┌──────────────┐   授权登录   ┌──────────────────────┐
│ Facebook 用户 │───────────►│ Facebook  App         │
│ (管理员)      │            │ app_id + app_secret   │
└──────────────┘            └──────────┬───────────┘
                                      │ Bob (User) 作为 Page Admin
                                      ▼
      ┌───────────────────────────────────────────────┐
      │         Facebook Page（粉丝页）                │
      │  page_id = 102290129340398                    │
      │  权限: pages_show_list / pages_read_engagement│
      │         pages_manage_meta / pages_manage_posts│
      │  ┌─────────────────────────────────────────┐  │
      │  │ Instagram 商业账号 (Business/Creator)    │  │
      │  │ ig-user-id = 17841400000000000          │  │
      │  │ 应用权限: instagram_basic               │  │
      │  │            instagram_manage_comments    │  │
      │  │            instagram_manage_insights    │  │
      │  │            instagram_content_publish    │  │
      │  │            instagram_manage_messages    │  │
      │  └─────────────────────────────────────────┘  │
      └───────────────────────────────────────────────┘
```

**绑定唯一的官方路径：** 在 Instagram App / Facebook Page Settings 中完成"链接 Instagram 账号"。绑定后，granular token（直播间 / 元数据）等才可能返回 `instagram_business_account` 字段。

### 1.4 认证与权限体系

#### 1.4.1 令牌类型与层级

| 令牌 | 获得方式 | 适用场景 | 生命周期 |
|------|---------|---------|---------|
| User Access Token | OAuth 授权登录（`/oauth/access_token`，包含 FB Login） | 开发/测试、代表某管理员调用 | 2 小时短期 + 60 天长期（页面 tokens 不自动刷新） |
| Page Access Token | `GET /{page-id}?fields=access_token`（需用户 token） | 以 Page 身份读取/互动 | 长期，与用户 token 绑定 |
| System User Token（System User） | Business Manager 创建系统用户 | 生产服务器无交互调用 | 长期，到期需手动续 |
| Instagram Graph Token | 与普通 User/Page token 相同；**IG Graph API 不接受 App Token** | IG 数据 | 同 user/page token |

> **切记：** Instagram Graph API **不支持应用级令牌（App Token）**，只支持 user-level 或 page-level token；且**发布内容（POST media）要求使用拥有相应权限的 user token 或 system user token**。

#### 1.4.2 应用权限（App Review 申请）

以下权限在 App 内申请（部分需通过 App Review 才能在生产使用）：

| 权限 | 用途 | 备注 |
|------|------|------|
| `instagram_basic` | 读取 IG 用户基本资料、被绑定 Page 下的 IG 账号 | 默认授予；**成员/管理员**可见 |
| `instagram_manage_comments` | 读取/回复/删除/隐藏评论与回复 | 需公开内容, App Review |
| `instagram_manage_insights` | 读取账号与媒体 Insights | 需 App Review |
| `instagram_content_publish` | 创建与发布媒体内容 | 需 App Review |
| `instagram_manage_messages` | 收发明信片 DM（Messenger 集成） | 可选 |
| `pages_read_engagement` | 读取 Page 上的互动数据 | Page 权限 |
| `pages_manage_posts` | 以 Page 身份发帖 | 若需以 Page 身份 |
| `pages_show_list` | `GET /me/accounts` 列出可见 Page | 读取 Page 列表 |

> ⚠️ 权限分为 **App 权限（application permission，授予 App）** 与 **Page 权限（角色权限，授予某个 Page）**。调用 IG 端点时系统会同时校验两者——**App 通过审核但你不是 Page 管理员，照样报权限错误**。

#### 1.4.3 获取 instagram_business_account id

`instagram_business_account` 字段是 Page 上的一个扩展字段，返回的是挂在 Page 下的 IG 商业账号 `ig-user-id`：

```
GET /{page-id}?fields=instagram_business_account&access_token=PAGE_ACCESS_TOKEN
```

```json
{
  "instagram_business_account": {
    "id": "17841400000000000"
  },
  "id": "102290129340398"
}
```

若返回为空/缺失，说明该 Page **尚未绑定**任何 Instagram 商业账号 → 属"绑定层"问题（详见第四节）。

---

### 1.5 内容对象模型

Instagram Graph API 的对象模型围绕"**媒体容器 → 已发布媒体**"这套两段式设计展开，这是理解全 API 的钥匙。

```
对象模型
┌─────────────────────── Instagram 媒体内容 ───────────────────────┐
│                                                                   │
│   Container（容器，未发布）          Media（已发布）              │
│   ┌──────────────────────┐         ┌────────────────────────┐   │
│   │ POST /{ig}/media      │ 发布 ──►│ POST /{ig-container-id}│   │
│   │ 返回 container id     │ 关联    │ 返回 media id          │   │
│   │ status_code:          │         │ status_code:           │   │
│   │  EXPIRED/FINISHED/    │         │  EXPIRED/FINISHED/     │   │
│   │  IN_PROGRESS/PUBLISHED│         │  IN_PROGRESS/PUBLISHED │   │
│   └──────────────────────┘         └────────────────────────┘   │
│            │图片/视频/轮播/Reels                                     │
└───────────────────────────────────────────────────────────────────┘

其他对象
├── Comment（评论/回复）  ├── Hashtag（话题 id）  ├── Insights（指标）
├── Follower/Following（关注关系）  └── Webhook Event（实时事件）
```

**为什么是"容器→发布"两段式？** 因为上传到 IG 的媒体需要后台**处理（transcoding / 转码、审核、存储）**。直接创建并不等于发布：你先用 `image_url`/`video_url` 等参数**创建容器**，IG 后台处理该容器（status_code: `IN_PROGRESS`），你再**显式发布**容器，得到最终 media id。处理需要时间（图片数秒~数十秒、视频几十秒~数分钟），因此必须轮询 `status_code` 才能安全发布。

### 1.6 统一请求 / 响应约定

- **Base URL**：`https://graph.facebook.com/v{API_VERSION}`
- **版本**：本文以 `v19.0` 为主，`v20.0`、`v21.0` 兼容；建议始终在 URL 中带版本号。
- **鉴权**：绝大多数端点接受 `?access_token=TOKEN` 查询参数，或 `Authorization: Bearer TOKEN` 头。
- **字段过滤**：`?fields=a,b,c` 减少带宽；Instagram 部分对象**默认不返回所有字段**，必须显式 `fields`。
- **错误格式**：HTTP 200（业务错误在 body）/ 4xx / 5xx 都有规范错误 JSON：
```json
{
  "error": {
    "message": "(#10) ...",
    "type": "OAuthException",
    "code": 10,
    "error_subcode": 33
  }
}
```

### 1.7 本文角色约定

- `{ig-user-id}`：Instagram 商业账号 IGID（`1784xxxxxxxxxxxx` 开头）
- `{page-id}`：Facebook Page ID
- `{media-id}` / `{ig-media-id}`：已发布媒体或容器的 id
- `{comment-id}`：评论 id
- `{ig-hashtag-id}`：话题 id
- `${IG_USER_ID}`、`${PAGE_ID}`、`${TOKEN}` 等为 shell/环境占位，实际用你自己的值替换

---

## 二、深度原理解析

> 本部分为全文重点之一，逐条拆解 Instagram Graph API 的核心机制，并给出可直接运行的 `curl` 示例与 Python 封装思路。

### 2.1 认证与 access_token 生命周期

#### 2.1.1 OAuth 授权流程（拿到 User Access Token）

Instagram Graph API 的令牌来自 **Facebook OAuth 2.0 / FB Login**（不是独立的 Instagram OAuth）。四种拿 token 的方式：

**方式 A：FB Login OAuth（交互式，推荐用于开发/测试）**

1. 用户在浏览器访问授权页：
```
https://www.facebook.com/v19.0/dialog/oauth?
  client_id={app-id}
  &redirect_uri={redirect-uri}
  &state={state}
  &scope=instagram_basic,pages_show_list,pages_read_engagement
```
2. 用户授权后跳回 `redirect_uri?code={auth-code}&state={state}`；
3. 用授权码换短期 token：
```bash
curl -X GET "https://graph.facebook.com/v19.0/oauth/access_token" \
  -d "client_id={app-id}" \
  -d "client_secret={app-secret}" \
  -d "redirect_uri={redirect-uri}" \
  -d "code={auth-code}"
```
返回 `{"access_token": "...", "token_type": "bearer", "expires_in": 7200}`（短期 2 小时）。

**方式 B：将短期 token 换成 60 天长期 token**
```bash
curl -X GET "https://graph.facebook.com/v19.0/oauth/access_token" \
  -d "grant_type=fb_exchange_token" \
  -d "client_id={app-id}" \
  -d "client_secret={app-secret}" \
  -d "fb_exchange_token={SHORT_LIVED_TOKEN}"
```

**方式 C：App Secret Proof（生产加固，可选）**

对每个请求额外附上 HMAC 签名的 `appsecret_proof`：
```python
import hashlib, hmac
proof = hmac.new(
    APP_SECRET.encode(), TOKEN.encode(), hashlib.sha256
).hexdigest()
# 之后每次请求带 &appsecret_proof={proof}
```

**方式 D：System User Token（生产服务器无交互）**

在 Business Manager → System Users 创建系统用户，分配 Page/广告账号权限，生成长期 token。适合定时任务、批量发帖等无人值守场景。

#### 2.1.2 令牌能做什么——几类令牌的能力矩阵

| 端点/操作 | User Token | Page Token | System User Token |
|-----------|-----------|------------|-------------------|
| `GET /me/accounts`（列 Page） | ✅ 需 `pages_show_list` | ❌ | ✅ |
| `GET /{page-id}?fields=instagram_business_account` | ✅ 需 `pages_read_engagement` | ✅ | ✅ |
| 读取媒体 / 评论 | ✅ 需 `instagram_basic`+`instagram_manage_comments` | ✅ | ✅ |
| 创建容器 / 发布（POST media） | ✅ 需 `instagram_content_publish` | ⚠️ 视权限 | ✅ 推荐 |
| 读取 Insights | ✅ 需 `instagram_manage_insights` | ✅ | ✅ |
| Hashtag 搜索/聚合 | ✅ | ✅ | ✅ |

> **生产建议：** 无人值守批量发帖 → 用 **System User Token**（权限固定、不因人员离职而失效，但需在 BM 里挂到对应 Page/AD account）。多人协作开发 → 用跑在**每个管理员自己账号**下的 User Token。

#### 2.1.3 令牌失效的常见信号

- `(#10) ... The session has been invalidated ...` → 用户在设置里撤销了授权；
- `(#190) Error validating access token ...` → token 过期（60 天）或格式错误；
- `(#200) ... Permissions error` → 令牌有效但权限不足。

> 需本地缓存 token 并实现【到期前 N 天告警 + 静默续期】。系统用户 token 无自动续期，必须维护续期任务（详见第三节）。

---

### 2.2 `/me/accounts`：列出可见 Page 与关联 IG 账号

`GET /me/accounts` 返回当前 token 对应用户**能见到的所有 Page**。结合 `fields=instagram_business_account` 可一次拿到每个 Page 的 IG 商业账号 id。

```bash
# 列出可见 Page，并展开每个 Page 挂载的 IG 商业账号
curl -X GET "https://graph.facebook.com/v19.0/me/accounts" \
  -d "access_token=${TOKEN}" \
  -d "fields=id,name,instagram_business_account,access_token"
```

响应（节选）：
```json
{
  "data": [
    {
      "id": "102290129340398",
      "name": "Ryan Digital Lab",
      "instagram_business_account": { "id": "17841400000000000" },
      "access_token": "EAB...page-level-token..."
    },
    {
      "id": "102290129340999",
      "name": "Second Page",
      "instagram_business_account": null
    }
  ]
}
```

> 关键点：
> 1. `instagram_business_account` 为 `null` 说明该 Page **没绑定 IG 商业账号**；
> 2. 只有你（token 用户）是 Page **admin** 且 App 有 `instagram_basic` + `pages_show_list` 时，列表才齐全；
> 3. 返回的 `access_token` 是 **Page Access Token**，可用于以该 Page 身份调用，但 IG 端操作最好用用户 token 或系统用户 token。

**Python 封装示例**（与 `scripts/ad_platform_api.py` 中 `meta_list_accounts` 风格一致）：
```python
def meta_list_instagram_accounts(self, **kwargs) -> list:
    """列出当前 token 下所有可见 Page 及其挂载的 IG 商业账号。
    对应 GET /me/accounts?fields=id,name,instagram_business_account"""
    token = self.get_token()
    resp = self.request(
        "GET", "me/accounts",
        params={
            "access_token": token,
            "fields": "id,name,instagram_business_account,access_token",
            **kwargs,
        },
    )
    accounts = []
    for page in resp.json().get("data", []):
        accounts.append({
            "page_id": page.get("id"),
            "page_name": page.get("name"),
            "page_access_token": page.get("access_token"),
            "ig_user_id": (page.get("instagram_business_account") or {}).get("id"),
        })
    return accounts
```

---

### 2.3 获取 IG 用户（Business Account）资料

拿到 `ig-user-id` 后，用 `GET /{ig-user-id}` 读取账号资料。**Instagram 用户对象没有默认字段，必须显式 `fields`。**

```bash
curl -X GET "https://graph.facebook.com/v19.0/17841400000000000" \
  -d "fields=id,username,followers_count,follows_count,media_count,biography,name,profile_picture_url,website,ig_id" \
  -d "access_token=${TOKEN}"
```

响应：
```json
{
  "id": "17841400000000000",
  "username": "ryandigitallab",
  "followers_count": 18240,
  "follows_count": 512,
  "media_count": 638,
  "biography": "数字营销与 Agent 技术",
  "name": "Ryan Digital Lab",
  "profile_picture_url": "https://scontent...",
  "website": "https://example.com",
  "ig_id": "12345678901234567"
}
```

**字段说明：**

| 字段 | 说明 | 备注 |
|------|------|------|
| `id` | IG 商业账号 Graph id（IGID） | `1784...` 开头 |
| `username` | 账号用户名（@handle） | 可通过 `instagram_basic` 读取 |
| `name` | 显示名 | 需 `instagram_basic` |
| `biography` | 个人简介 | — |
| `followers_count` / `follows_count` | 粉丝数 / 关注数 | **公开字段**，任何人可读 |
| `media_count` | 已发布媒体数 | — |
| `profile_picture_url` | 头像 URL | 可能需 `instagram_basic` |
| `website` | 主页链接 | — |
| `ig_id` | Instagram 公开数字 id（IGDBID） | 可用于网页端/公开接口映射 |

**Python 封装**（`meta_get_ig_user`）：
```python
def meta_get_ig_user(self, ig_user_id: str, **kwargs) -> dict:
    """读取 IG 商业账号资料。
    对应 GET /{ig-user-id}?fields=..."""
    return self.request(
        "GET", ig_user_id,
        params={
            "access_token": self.get_token(),
            "fields": "id,username,followers_count,follows_count,"
                      "media_count,biography,name,profile_picture_url,"
                      "website,ig_id",
            **kwargs,
        },
    ).json()
```

---

### 2.4 创建媒体容器：`POST /{ig-user-id}/media`

Instagram 的"发帖"被拆成 **创建容器（Container）→ 发布容器（Publish）** 两步。第一步创建容器，第二步发布。下面是不同媒体类型的容器创建。

#### 2.4.1 发布图片（IMAGE）

```bash
curl -X POST "https://graph.facebook.com/v19.0/17841400000000000/media" \
  -d "image_url=https://example.com/img/product-1.jpg" \
  -d "caption=夏季大促 5 折起 #summersale #fashion #sale" \
  -d "access_token=${TOKEN}"
```
响应：`{"id": "17863000000000001"}`（这是 **container id**，尚未发布）。

**必填/可选参数表（IMAGE）：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `image_url` | ✅ | 公开可访问的图片 URL（IG 后台需抓取） |
| `caption` | ❌ | 文案，可含 hashtag 与 @mention |
| `access_token` | ✅ | 有 `instagram_content_publish` 的 token |
| `is_reel` | ❌ | 是否作为 Reel 发布；传 false 表示普通帖子 |
| `location_id` | ❌ | 关联的地点 id（需先搜索地点） |

> `image_url` 必须是**公开可访问**的 URL（不能被登录墙/鉴权拦截），且**内容不得违反版权/社区规范**，否则容器会被判 `EXPIRED` 或被拒。

#### 2.4.2 发布视频（VIDEO）

```bash
curl -X POST "https://graph.facebook.com/v19.0/17841400000000000/media" \
  -d "media_type=VIDEO" \
  -d "video_url=https://example.com/video/clip-1.mp4" \
  -d "caption=产品演示视频 #demo #video" \
  -d "thumb_offset=2000" \
  -d "access_token=${TOKEN}"
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `media_type=VIDEO` | ✅ | 标记为视频 |
| `video_url` | ✅ | 公开 MP4 URL |
| `caption` | ❌ | 文案 |
| `thumb_offset` | ❌ | 视频内秒数，用于选作封面帧 |
| `copyright_check` | ❌ | true 时触发版权检查 |

> 视频容器处理时间较长（几十秒~数分钟），**必须轮询 status_code** 再发布（见 2.6）。

#### 2.4.3 发布轮播（CAROUSEL）

轮播需要**先为每张图创建一个"子容器"（`is_carousel_item=true`）**，再把子容器 id 组装成一个轮播容器：

**第 1 步：为每张图片创建子容器**
```bash
curl -X POST "https://graph.facebook.com/v19.0/17841400000000000/media" \
  -d "image_url=https://example.com/img/c1.jpg" \
  -d "is_carousel_item=true" \
  -d "access_token=${TOKEN}"
# → {"id": "1787xxxxx_child_1"}
```

**第 2 步：组装轮播容器**
```bash
curl -X POST "https://graph.facebook.com/v19.0/17841400000000000/media" \
  -d "media_type=CAROUSEL" \
  -d "children=1787xxxxx_child_1,1787xxxxx_child_2,1787xxxxx_child_3" \
  -d "caption=三图轮播 展现多角度 #lookbook" \
  -d "access_token=${TOKEN}"
# → {"id": "17863000000000002"}（轮播容器）
```

> 约束：轮播**图片 2~10 张**，不能混视频；所有子容器需先完成处理（`status_code=FINISHED`）再组装，否则整体处理失败。

#### 2.4.4 发布 Reels

Reels 本质是"短竖屏视频"，可在容器阶段通过 `media_type=REELS`（或 `is_reel=true` + `media_type=VIDEO`）创建：

```bash
curl -X POST "https://graph.facebook.com/v19.0/17841400000000000/media" \
  -d "media_type=REELS" \
  -d "video_url=https://example.com/reel/demo.mp4" \
  -d "caption=竖屏 Reel 测试 #reel #tutorial" \
  -d "share_to_feed=true" \
  -d "access_token=${TOKEN}"
```

| 参数 | 说明 |
|------|------|
| `media_type=REELS` | 标记 Reels |
| `share_to_feed` | 是否同步分享到动态流（feed） |
| `copyright_check` | 版权检查 |
| `location_id` / `collaborators` / `audio_name` | 可选增强 |

#### 2.4.5 容器创建的状态机

容器创建后，可用 `GET /{container-id}?fields=status_code` 查询处理状态：

| status_code | 含义 | 处理 |
|-------------|------|------|
| `EXPIRED` | 容器已过期（24 小时未发布，或被拒） | 重建容器 |
| `FINISHED` | 处理完成，可发布 | 进入发布 |
| `IN_PROGRESS` | 仍在后台处理 | 等待轮询 |
| `PUBLISHED` | 已发布成媒体 | 完成 |
| `ERROR` | 处理失败 | 查看 `status`/`error_message` 重建 |

```bash
curl -X GET "https://graph.facebook.com/v19.0/17863000000000001" \
  -d "fields=status_code,status" \
  -d "access_token=${TOKEN}"
# → {"status_code":"FINISHED","status":"FINISHED","id":"17863000000000001"}
```

---

### 2.5 发布容器：`POST /{ig-container-id}`（PUBLISH 关系）

容器处理完成后（`status_code=FINISHED`），用**发布端点**把它变成已发布媒体：

```bash
curl -X POST "https://graph.facebook.com/v19.0/17863000000000001" \
  -d "access_token=${TOKEN}"
```
响应：`{"id": "17920786867118320"}`（这是**最终的 media id**）。

> ✅ "`POST /{ig-media-id}` 也叫媒体发布关系（PUBLISH relationship）"——**同一容器只会发布一次**；重复发布同一 container id 会被拒绝（容器一旦 `PUBLISHED` 或 `EXPIRED` 即不可再用）。

**发布后的校验：**
```bash
curl -X GET "https://graph.facebook.com/v19.0/17920786867118320" \
  -d "fields=id,caption,media_type,timestamp,permalink,children,comments_count,like_count" \
  -d "access_token=${TOKEN}"
```

> ⚠️ 发布 **只对"公开（Public）"的 IG 商业账号生效**。若账号为**私密（Private/Hide: Off）**，容器会因隐私限制而无法发布或发布后被隐藏——这是最常见的"能创建、不能发布"的坑（详见第四节 4.3）。

---

### 2.6 内容发布时序（Media Publishing Timeline）

下图展示从"创建容器"到"帖子可见"的完整时序，重点标注了**必须轮询**与**必须杜绝**的点：

```
【多媒体发布完整时序】
 Client                          IG Graph API                    IG 后台
   │                                   │                            │
   │ POST /{ig}/media (image_url)      │                            │
   ├──────────────────────────────────►│                            │
   │   {container_id, status=…}        │                            │
   │◄──────────────────────────────────┤                            │
   │                                   │     转码/审核/落库          │
   │                                   │◄───────────────────────────│
   │                                   │   (图片: 数秒~数十秒;       │
   │ GET /{container}?fields=status_code ...                         │
   │────────────────────►              │                            │
   │   IN_PROGRESS ...                 │                            │
   │◄────────────────────              │                            │
   │  (轮询: status_code == FINISHED)  │                            │
   │                                   │  ┌ 不能 FINISHED 前发布    │
   │ POST /{container_id}  (发布)      │                            │
   ├──────────────────────────────────►│                            │
   │   {media_id}                      │   持久化 + 索引 + 通知      │
   │◄──────────────────────────────────┤◄───────────────────────────│
   │                                   │                            │
   │ GET /{media_id}?fields=permalink  │                            │
   ├──────────────────────────────────►│                            │
   │   {permalink: "https://…/p/XXX/"} │                            │
   │◄──────────────────────────────────┤                            │
   ▼                                   ▼                            ▼
```

**时序要点（production 必背）：**

1. **容器创建 ≠ 发布**。`POST media` 只产出 container id；
2. **发布前必须等 `status_code=FINISHED`**。视频尤其慢；太早发布会得到 `ERROR` / 空发布的 container；
3. **容器 24 小时有效**，超时 `EXPIRED`，需重建；
4. **同样的 image/video URL 短时间内重复创建容器**可能被去重（同一 URL 视为重复内容），做内容日历批量发帖时要给资源加 AV/缓存破坏参数；
5. 发布成功后**再次查询容器/媒体**确认 `permalink` 可用。

**建议的轮询逻辑（Python）：**
```python
import time

def wait_container_ready(self, container_id: str, timeout: float = 300.0,
                         interval: float = 5.0) -> str:
    """轮询容器直到 FINISHED / PUBLISHED / EXPIRED / ERROR。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = self.request(
            "GET", container_id,
            params={
                "access_token": self.get_token(),
                "fields": "status_code,status",
            },
        ).json().get("status_code")
        if status in ("FINISHED", "PUBLISHED"):
            return status
        if status in ("EXPIRED", "ERROR"):
            raise RuntimeError(f"container {container_id} -> {status}")
        time.sleep(interval)
    raise TimeoutError(f"container {container_id} 轮询超时")
```

---

### 2.7 评论（Comments）与回复

评论端点允许读取某个媒体下的评论、回复评论、隐藏/删除、以及用 @提及 进行互动。**前提权限：`instagram_manage_comments`**，且只对**公开媒体**的评论可读（私有内容除外）。

#### 2.7.1 读取媒体评论：`GET /{ig-media-id}/comments`

```bash
curl -X GET "https://graph.facebook.com/v19.0/17920786867118320/comments" \
  -d "fields=id,text,timestamp,username,like_count,replies_count" \
  -d "access_token=${TOKEN}"
```

响应：
```json
{
  "data": [
    {
      "id": "17873440459141069",
      "text": "这个多少钱？",
      "timestamp": "2026-08-13T12:34:56+0000",
      "username": "user_a",
      "like_count": 3,
      "replies_count": 1
    }
  ],
  "paging": { "cursors": { "before": "QVF...", "after": "QVFI..." }, "next": "https://..." }
}
```

> 评论可能被限流/隐藏，默认只返回"公开可见 + 你有交互权限"的条目。`replies_count` 表示该评论下的回复数，但不内联展开。

#### 2.7.2 分页（Paging）

Instagram 端点分页用游标（cursors）。编程时用 `paging.next` / 传入 `after` 游标继续翻页：

```bash
curl -X GET "https://graph.facebook.com/v19.0/17920786867118320/comments" \
  -d "fields=id,text,username" \
  -d "limit=50" \
  -d "after=QVFI..." \
  -d "access_token=${TOKEN}"
```

**Python 分页封装：**
```python
def meta_list_ig_comments(self, media_id: str, fields: str = "id,text,username,timestamp",
                          limit: int = 100, **kwargs) -> list:
    """分页读取某条媒体下的评论。"""
    token = self.get_token()
    collected, after = [], None
    while True:
        params = {
            "access_token": token, "fields": fields, "limit": limit,
            **kwargs,
        }
        if after:
            params["after"] = after
        data = self.request("GET", f"{media_id}/comments",
                            params=params).json()
        collected.extend(data.get("data", []))
        nxt = (data.get("paging") or {}).get("next")
        if not nxt:
            break
        after = (data.get("paging") or {}).get("cursors", {}).get("after")
        if not after:
            break
    return collected
```

#### 2.7.3 发布评论回复：`POST /{ig-comment-id}/replies`

```bash
curl -X POST "https://graph.facebook.com/v19.0/17873440459141069/replies" \
  -d "message=您好，这款 899 元，今天下单顺丰包邮。#sale" \
  -d "access_token=${TOKEN}"
# → {"id": "17873440459141070"}
```

> 回复可含 **@提及**（`@username`）与 **hashtag**。注意：**每条评论的回复频率受限流**（见 2.9 限流小节），高频机器人回复极易触发 `(#4) Application request limit reached` 或评论级额度。

**Python 封装（`meta_reply_ig_comment`）：**
```python
def meta_reply_ig_comment(self, comment_id: str, message: str, **kwargs) -> dict:
    """回复一条 IG 评论。对应 POST /{comment-id}/replies"""
    return self.request(
        "POST", f"{comment_id}/replies",
        params={"access_token": self.get_token(), "message": message, **kwargs},
    ).json()
```

#### 2.7.4 删除 / 隐藏评论

**删除（永久移除）：**
```bash
curl -X DELETE "https://graph.facebook.com/v19.0/17873440459141069" \
  -d "access_token=${TOKEN}"
```
> 删除是用户级操作：**只能删除"自己账号发出的评论或回复"**；别人在你帖子下的评论只能**隐藏**，不能物理删除。

**隐藏（is_hidden，软隐藏他人评论）：**

```bash
curl -X POST "https://graph.facebook.com/v19.0/17873440459141069" \
  -d "is_hidden=true" \
  -d "access_token=${TOKEN}"
```

| 方法 | 作用对象 | 效果 |
|------|---------|------|
| `DELETE /{comment-id}` | 自己发的评论/回复 | 永久删除 |
| `POST /{comment-id}` with `is_hidden=true` | 他人评论 | 隐藏（原作者/账号可再取消隐藏） |
| `POST /{comment-id}` with `is_hidden=false` | 已隐藏评论 | 取消隐藏 |

#### 2.7.5 用 @提及 触发互动

在 `message` / `caption` 中写入 `@username`，即可 @ 该 IG 用户（前提对方是公开账号）。Webhook 会把 `mentions` 事件推送给被 @ 的对象（见 2.11）。**想做"@ 客服/品牌"联动，这是最常用的机制。**

---

### 2.8 Hashtag 搜索：`GET /{ig-user-id}/hashtags_search?q=`

Hashtag 功能先把**文本 hashtag** 解析成**数字 hashtag id**，再用数字 id 做聚合查询。第一步是搜索：

```bash
curl -X GET "https://graph.facebook.com/v19.0/17841400000000000/hashtags_search" \
  -d "q=summersale" \
  -d "user_id=17841400000000000" \
  -d "access_token=${TOKEN}"
```
响应：
```json
{
  "data": [
    { "id": "17843812461040521", "name": "summersale" },
    { "id": "17843812461040999", "name": "summersale2026" }
  ]
}
```

**要点：**
- 必须带 `user_id={ig-user-id}` 参数（部分版本要求）；
- `q` 是**不含 `#` 前缀**的关键词；
- 返回按匹配度排序的多个 hashtag，取 `data[0]` 通常是精确匹配；
- **Hashtag 搜索有严格限制**：需创建者/社区（Creator/Community）账号身份、App Review、且 `q` 需要是稳定存在的 tag；盲目搜随机字符串可能得到空结果并被限流。

**Python 封装（`meta_search_ig_hashtags`）：**
```python
def meta_search_ig_hashtags(self, ig_user_id: str, q: str, **kwargs) -> list:
    """搜索 hashtag，返回 [{id, name}]。对应 GET /{ig-user-id}/hashtags_search"""
    return self.request(
        "GET", f"{ig_user_id}/hashtags_search",
        params={"access_token": self.get_token(), "q": q,
                "user_id": ig_user_id, **kwargs},
    ).json().get("data", [])
```

---

### 2.9 Hashtag 聚合：Top / Recent Media

拿到 `ig-hashtag-id` 后，可查询该话题下的**顶级媒体（top_media）**与**最近媒体（recent_media）**。权限：`instagram_basic` + 创建者/社区身份；App 需通过 Hashtag 相关审核。

**Top Media：**
```bash
curl -X GET "https://graph.facebook.com/v19.0/17843812461040521/top_media" \
  -d "user_id=17841400000000000" \
  -d "fields=id,caption,media_type,permalink,like_count,comments_count,media_url,timestamp" \
  -d "access_token=${TOKEN}"
```

**Recent Media：**
```bash
curl -X GET "https://graph.facebook.com/v19.0/17843812461040521/recent_media" \
  -d "user_id=17841400000000000" \
  -d "fields=id,caption,media_type,permalink,like_count,comments_count,media_url,timestamp" \
  -d "access_token=${TOKEN}"
```

响应（data 数组封装，结构与 media 一致）：
```json
{
  "data": [
    {
      "id": "17920786867118320",
      "caption": "夏日穿搭 #summersale",
      "media_type": "IMAGE",
      "permalink": "https://www.instagram.com/p/XXXX/",
      "like_count": 321,
      "comments_count": 12,
      "media_url": "https://scontent...",
      "timestamp": "2026-08-12T08:00:00+0000"
    }
  ],
  "paging": { "cursors": {...}, "next": "https://..." }
}
```

**聚合用途（业务场景）：**
1. **话题趋势监控**：追踪竞品/品牌话题的 top_media 点赞评论，判断热度；
2. **UGC 素材挖掘**：收集用户晒图作二次传播素材；
3. **竞选 campaign tag**：统计某活动话题下的互动总量；
4. **KOL 识别**：top_media 作者即高影响力账号。

> ⚠️ **2024 年后官方对 Hashtag 端点大幅收紧**：`top_media` / `recent_media` **不再对普通 App 开放**，仅限"创建者/社区（Creator/Community）"身份，且必须经过严格 App Review。大众业务若拿不到该权限，Hashtag 仅能用于**内容发布时的标签**、以及少数已被授权的用例——计划前先确认你的 App 是否具备相应权限，否则会持续 `(#100)` 报错。

**Python 封装（聚合翻页）：**
```python
def _page_hashtag_media(self, hashtag_id: str, ig_user_id: str, kind: str,
                        fields: str, **kwargs) -> list:
    """kind ∈ {top_media, recent_media}，自动翻页聚合。"""
    token = self.get_token()
    result, after = [], None
    while True:
        params = {"access_token": token, "user_id": ig_user_id,
                  "fields": fields, **kwargs}
        if after:
            params["after"] = after
        body = self.request("GET", f"{hashtag_id}/{kind}",
                            params=params).json()
        result.extend(body.get("data", []))
        nxt = (body.get("paging") or {}).get("next")
        if not nxt:
            break
        after = (body.get("paging") or {}).get("cursors", {}).get("after")
        if not after:
            break
    return result

def meta_aggregate_ig_hashtag(self, hashtag_id: str, ig_user_id: str,
                              kind: str = "top_media", **kwargs) -> list:
    """聚合某 hashtag 下的 top/recent media。"""
    return self._page_hashtag_media(
        hashtag_id, ig_user_id, kind,
        "id,caption,media_type,permalink,like_count,comments_count,"
        "media_url,timestamp", **kwargs)
```

---

### 2.10 关注 / 取消关注（Follow / Unfollow）

IG Graph API 可让**你管理的 IG 商业账号**关注/取消关注其他账号。权限：`instagram_basic` + 公开目标账号。

**关注：**
```bash
curl -X POST "https://graph.facebook.com/v19.0/17841400000000000/follows" \
  -d "user_id=1784ANOTHER_ACCOUNT_ID" \
  -d "access_token=${TOKEN}"
```

**取消关注：**
```bash
curl -X DELETE "https://graph.facebook.com/v19.0/17841400000000000/follows" \
  -d "user_id=1784ANOTHER_ACCOUNT_ID" \
  -d "access_token=${TOKEN}"
```

**读取关注列表：**
```bash
curl -X GET "https://graph.facebook.com/v19.0/17841400000000000/following" \
  -d "fields=id,username" \
  -d "access_token=${TOKEN}"

curl -X GET "https://graph.facebook.com/v19.0/17841400000000000/followers" \
  -d "fields=id,username,followers_count" \
  -d "access_token=${TOKEN}"
```

> ⚠️ **关注/取关是高敏感操作**：超过一定频率/数量会被 Instagram 判定为**自动化灌粉/互粉**，导致账号风控、临时限制甚至封禁。**任何批量关注脚本都应严格限速（如每小时 ≤ 几次），并强烈建议人工审批白名单。**

**Python 封装（`meta_list_ig_followers` 与关注工具）：**
```python
def meta_list_ig_followers(self, ig_user_id: str, fields: str = "id,username",
                           limit: int = 100, **kwargs) -> list:
    """分页读取粉丝列表。对应 GET /{ig-user-id}/followers"""
    token, result, after = self.get_token(), [], None
    while True:
        params = {"access_token": token, "fields": fields, "limit": limit,
                  **kwargs}
        if after:
            params["after"] = after
        body = self.request("GET", f"{ig_user_id}/followers",
                            params=params).json()
        result.extend(body.get("data", []))
        nxt = (body.get("paging") or {}).get("next")
        if not nxt:
            break
        after = (body.get("paging") or {}).get("cursors", {}).get("after")
    return result

def meta_ig_follow_user(self, ig_user_id: str, target_user_id: str,
                        action: str = "follow", **kwargs) -> dict:
    """关注/取关。action ∈ {follow, unfollow}"""
    url = f"{ig_user_id}/follows"
    params = {"access_token": self.get_token(),
              "user_id": target_user_id, **kwargs}
    if action == "unfollow":
        return self.request("DELETE", url, params=params).json()
    return self.request("POST", url, params=params).json()
```

---

---

### 2.11 Insights（账号级与媒体级）

Insights 是 Instagram Graph API 的"数据金矿"，权限：`instagram_manage_insights`。分两类：**账号级**（整个账号一段时间的表现）与**媒体级**（单条帖子表现）。

#### 2.11.1 账号级 Insights：`GET /{ig-user-id}/insights`

```bash
curl -X GET "https://graph.facebook.com/v19.0/17841400000000000/insights" \
  -d "metric=reach,impressions,profile_views,follower_count" \
  -d "period=day" \
  -d "since=2026-08-01" \
  -d "until=2026-08-14" \
  -d "access_token=${TOKEN}"
```

响应（按 metric 分组，每项含 `values[]` 时间序列）：
```json
{
  "data": [
    {
      "name": "reach",
      "period": "day",
      "values": [
        { "end_time": "2026-08-01T07:00:00+0000", "value": 1234 },
        { "end_time": "2026-08-02T07:00:00+0000", "value": 987 }
      ]
    },
    { "name": "impressions", "period": "day", "values": [...] },
    { "name": "profile_views", "period": "day", "values": [...] },
    { "name": "follower_count", "period": "day", "values": [...] }
  ]
}
```

**账号级指标说明：**

| metric | 含义 | period | 备注 |
|--------|------|--------|------|
| `reach` | 触达人数（看到内容的独立用户数） | day | 核心增长指标 |
| `impressions` | 展示次数（含重复曝光） | day | ≥ reach |
| `profile_views` | 主页被查看次数 | day | 反映主页吸引力 |
| `follower_count` | 粉丝数 | **lifetime（仅一个值）** | trend 用 day 拉取序列 |
| `accounts_engaged` | 产生互动账号数 | day | 需更多权限 |

> ⚠️ **follower_count 只能 `period=lifetime`**（返回单个最新值），其它指标 `period=day` 才返回时间序列。**拉取间隔有上限（官方约 支持最近 30 天左右的 granular 日粒度）**。

**为什么"公开字段 vs 私有"影响 Insights：**
- `reach`、`impressions` 等只统计 **unique/登录态用户**口径；
- 若你的 IG 账号为**私密**，则 Insights **不可用**（`instagram_manage_insights` 需要 Business/Creator 且公开）。

**Python 封装（`meta_get_ig_insights`）：**
```python
def meta_get_ig_insights(self, ig_user_id: str,
                         metric: str = "reach,impressions,profile_views,follower_count",
                         period: str = "day", since: str = None,
                         until: str = None, **kwargs) -> dict:
    """读取账号级 Insights。对应 GET /{ig-user-id}/insights"""
    params = {
        "access_token": self.get_token(), "metric": metric,
        "period": period, **kwargs,
    }
    if since:
        params["since"] = since
    if until:
        params["until"] = until
    return self.request("GET", f"{ig_user_id}/insights",
                        params=params).json()
```

#### 2.11.2 媒体级 Insights：`GET /{ig-media-id}/insights`

```bash
curl -X GET "https://graph.facebook.com/v19.0/17920786867118320/insights" \
  -d "metric=engagement,saved,video_views,reach,impressions,shares,comments,likes" \
  -d "access_token=${TOKEN}"
```

响应：
```json
{
  "data": [
    { "name": "engagement", "period": "lifetime", "title": "Engagement",
      "description": "Total number of likes, comments, saves...",
      "values": [{ "value": 183 }] },
    { "name": "saved", "period": "lifetime", "values": [{ "value": 42 }] },
    { "name": "video_views", "period": "lifetime", "values": [{ "value": 15800 }] }
  ]
}
```

**媒体级指标说明：**

| metric | 适用媒体 | 含义 |
|--------|---------|------|
| `engagement` | 所有 | likes+comments+saves+shares 组合互动 |
| `reach` | IMAGE/VIDEO/REELS | 触达人数 |
| `impressions` | IMAGE/VIDEO/REELS | 展示次数 |
| `saved` | IMAGE/VIDEO/REELS | 收藏数（高价值信号） |
| `video_views` | VIDEO/REELS | 视频播放（≥3s 等口径） |
| `shares` | 所有 | 分享数 |
| `comments` | 所有 | 评论数 |
| `likes` | 所有 | 点赞数 |
| `profile_activity` | 账号级 | 主页动作 |
| `total_interactions` | REELS | 总互动（新版 Reels） |

> **媒体 Insights 为 `period=lifetime`**（媒体生命周期累计值），且**最早从媒体发布后约 1 时段起才有数据**；新发布媒体几分钟~几小时内在 API 中可能暂时无 insights，需要稍等（数据延迟详见第四节 4.6）。

**Python 封装（`meta_list_ig_media_insights`）：**
```python
def meta_list_ig_media_insights(self, media_id: str,
                                metric: str = "engagement,saved,video_views,"
                                              "reach,impressions,shares,"
                                              "comments,likes",
                                **kwargs) -> dict:
    """读取单条媒体 Insights。对应 GET /{ig-media-id}/insights"""
    return self.request(
        "GET", f"{media_id}/insights",
        params={"access_token": self.get_token(), "metric": metric, **kwargs},
    ).json()
```

#### 2.11.3 Insights 数据来源架构

```
Insights 数据链路
┌──────────────┐  埋点/日志   ┌────────────────┐  聚合   ┌────────────────┐
│  IG 客户端    │───────────►│  IG 后端事件流    │───────►│  Insights 存储   │
│ (App/Web)    │ 曝光/点击/  │  (impression,   │        │  (per-account,  │
│              │ 播放/关注   │   like, comment,│        │   per-media 累积)│
│              │            │   save, follow) │        │                 │
└──────────────┘            └────────────────┘        └───────┬─────────┘
                                                               │ 授权下拉（公开/私有）
                                                               ▼
                                        ┌───────────────────────────────┐
                                        │ Graph API  /{ig}/insights      │
                                        │ 账号级: reach/impressions/     │
                                        │         profile_views/         │
                                        │         follower_count         │
                                        │ 媒体级: engagement/saved/      │
                                        │         video_views/reach/     │
                                        │         impressions/shares/... │
                                        └───────────────────────────────┘
```

> 关键认知：Insights 是**聚合统计**，不是实时日志；存在**采集/聚合/上屏延迟**（分钟~小时级），且**只回看有限历史窗口**。做报表系统时必须在端侧缓存，并对"最新一天不完整"做处理。

---

### 2.12 Webhooks 实时订阅（comments.topic / mentions）

Webhooks 让 IG 在发生事件时**主动推送**给你的服务器，实现评论区客服、@ 提及监控等实时能力。订阅挂在 **App** 上，而不是某个 Page。

#### 2.12.1 支持的 IG 字段（fields）

| 字段名 | 推送事件 | 典型用途 |
|--------|---------|---------|
| `comments` | 有评论/回复发生时（可含 Replies） | 评论区监控、自动回复、风控 |
| `mentions` | 账号被 @ 提及 | KOL 营销、客服跟进 |
| `story_insights` | Story 洞察变化 | 内容表现监控 |
| `live_comments` | 直播评论 | 直播互动 |
| `comment_mentions` | 评论中的 @ | 延伸客服 |
| `message_deliveries` | DM 投递 | 私信客服 |

> `comments` 订阅可配置 `include_replies=true` 同时接收回复；只有**绑定到该 App 且你有权限的 IG 账号**的事件才会推送。

#### 2.12.2 订阅与验证（Verify Token）

在 Meta Developer Console 的 App → Webhooks → Instagram，或通过 API 设置订阅的 callback URL 与 verify token：

```
GET {your-callback}?hub.mode=subscribe
                    &hub.verify_token={your_verify_token}
                    &hub.challenge={random_string}
```

你的服务器需校验 `hub.verify_token` 是否匹配，匹配则回显 `hub.challenge`（订阅握手）。

**Python（Flask）Verify 端点：**
```python
from flask import Flask, request
app = Flask(__name__)

VERIFY_TOKEN = "your_verify_token"

@app.route("/ig/webhook", methods=["GET"])
def ig_webhook_verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403
```

#### 2.12.3 接收事件（POST 回调）

```python
import hashlib, hmac

def _sig_ok(payload: bytes, sig: str, app_secret: str) -> bool:
    expected = "sha1=" + hmac.new(
        app_secret.encode(), payload, hashlib.sha1
    ).hexdigest()
    return hmac.compare_digest(expected, sig)

@app.route("/ig/webhook", methods=["POST"])
def ig_webhook_event():
    # (可选) 校验 X-Hub-Signature 签名，防伪造
    sig = request.headers.get("X-Hub-Signature", "")
    if not _sig_ok(request.data, sig, APP_SECRET):
        return "Bad signature", 400
    body = request.get_json()
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            handle_ig_change(change.get("field"), change.get("value"))
    return "EVENT_RECEIVED", 200   # 必须尽快返回 200，超时会被重试
```

**comments 事件 payload 示例：**
```json
{
  "object": "instagram",
  "entry": [{
    "id": "1784...",
    "time": 1720000000,
    "changes": [{
      "field": "comments",
      "value": {
        "id": "17873440459141069",
        "media_id": "17920786867118320",
        "from": { "username": "user_a", "id": "17841400000000012" },
        "text": "请问能发货吗？",
        "timestamp": "2026-08-13T12:34:56+0000"
      }
    }]
  }]
}
```

> 生产要求：(1) 回调**必须在规定时间内返回 200**，否则平台会重试（幂等处理）；(2) 用 **X-Hub-Signature（HMAC-SHA1 of app secret）** 校验来源；(3) 消息可能重复推送，消费端需去重。

---

### 2.13 公开字段 vs 私有（Public vs Private）

Instagram Graph API 高度依赖"内容/账号是否公开"。理解这条线能解释一大半的怪异报错。

| 维度 | 公开（Public） | 私有（Private） |
|------|---------------|----------------|
| 谁可读媒体 | 任何人（API 授权内） | 仅粉丝，**API 基本不可读** |
| 发布 media（POST） | ✅ 可发布 | ❌ 容器无法发布（或发布后不可见） |
| Insights | ✅ 可用 | ❌ `instagram_manage_insights` 无意义 |
| Hashtag 索引 | ✅ tag 内容可聚合 | ❌ 私有内容不进公开 hashtag |
| 评论读取/回复 | ✅ 可读写 | ❌ 大多不可 |
| follower 列表 | ✅ | ❌/受限 |
| 关注他人 | ✅ 可关注公开账号 | — |

> **判定建议：** 生产前必须确认 IG 账号是 **Business/Creator + 公开**。若账号切回个人号或设为私密，几乎所有 IG Graph 端点都会失败。**这是"能跑通 Marketing API 却跑不通 IG 端点"的头号原因。**

---

### 2.14 速率限制（Rate Limits）与配额

IG Graph API 有限流，分两个层级：

1. **App-level / user-level 配额**：Graph API 按"每个用户每滚动小时"计数；超限返回：
```
(#4) Application request limit reached
```
```json
{ "error": { "code": 4, "error_user_msg": "Application request limit reached" } }
```

2. **特定操作粒度限流**：评论回复、关注/取关、发帖等有更严的滚动窗口限制。

**最佳实践（限流）：**
- 使用 `X-App-Usage` 响应头观察配额水位；
- 用**指数退避重试**（收到 4xx rate limit 后 sleep 递增）；
- 大数据量尽量用 **批量（Batch）** 或分页小步拉取；
- **柔和配额保护**：把高频调用（如洞察拉取）做成缓存 + 定时同步，而不是实时追查。

**带退避重试的请求封装：**
```python
import time, random

def _request_with_retry(self, method, url, params, retries=5):
    for attempt in range(retries):
        resp = self.request(method, url, params=params)
        err = resp.json().get("error", {})
        if err.get("code") in (4, 613, 80004) or resp.status_code in (400, 429):
            sleep = min(2 ** attempt + random.random(), 60)
            time.sleep(sleep)
            continue
        return resp
    raise RuntimeError(f"retry exhausted: {url}")
```

---

### 2.15 本部分小结（图表）

```
Instagram Graph API 能力地图
┌─────────────────────────────────────────────────────────────────┐
│  账号类        │  内容类            │  互动类       │  数据类       │
│  /me/accounts │  POST /{ig}/media  │  comments     │  /insights    │
│  /{ig-user-id}│  POST /{container} │  replies      │  账号级:reach │
│  follows      │  media_list        │  delete/hide  │  impressions  │
│  unfollows    │  carousel/reels    │  @mentions    │  profile_views│
│               │                     │  hashtags     │  follower_count│
│               │                     │  搜索/聚合     │  媒体级:engage│
│               │                     │                  saved/video  │
└─────────────────────────────────────────────────────────────────┘
  权限底座: instagram_basic + manage_comments + manage_insights
            + content_publish + pages_*  Page 绑定 + 公开账号
```
