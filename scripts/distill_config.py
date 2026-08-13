#!/usr/bin/env python3
"""
知识蒸馏配置
定义要蒸馏的开源项目列表
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DistillProject:
    """知识蒸馏项目配置"""
    
    # 项目名称
    name: str
    
    # GitHub URL
    github_url: str
    
    # 源文件路径（相对于仓库根目录）
    source_files: list[str]
    
    # 目标文档路径（相对于知识库根目录）
    target_docs: list[str]
    
    # 分类
    category: str
    
    # 核心价值描述
    core_value: str
    
    # 优先级（1-5，1 最高）
    priority: int = 3
    
    # 是否启用
    enabled: bool = True
    
    # 可选的分支名
    branch: str = "main"
    
    # 可选的标签（用于版本控制）
    tags: list[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


# 知识蒸馏项目列表
DISTILL_PROJECTS: list[DistillProject] = [
    # ===== LLM 推理框架 =====
    DistillProject(
        name="vLLM",
        github_url="https://github.com/vllm-project/vllm",
        source_files=[
            "vllm/v1/engine/llm_engine.py",
            "vllm/v1/core/sched/scheduler.py",
            "vllm/v1/worker/gpu_worker.py",
        ],
        target_docs=[
            "knowledge/agent-ai/vllm-engine-deep-dive.md",
            "knowledge/agent-ai/vllm-scheduler-deep-dive.md",
            "knowledge/agent-ai/vllm-gpu-worker-deep-dive.md",
        ],
        category="llm",
        core_value="生产级 LLM 推理优化 + GPU 调度策略",
        priority=1,
    ),
    
    # ===== 多 Agent 协作 =====
    DistillProject(
        name="MetaGPT",
        github_url="https://github.com/geekan/MetaGPT",
        source_files=[
            "metagpt/team.py",
            "metagpt/actions/action.py",
            "metagpt/roles/role.py",
        ],
        target_docs=[
            "knowledge/agent-ai/metagpt-team-deep-dive.md",
            "knowledge/agent-ai/metagpt-action-deep-dive.md",
            "knowledge/agent-ai/metagpt-role-deep-dive.md",
        ],
        category="agent",
        core_value="多 Agent 协作架构 + SOP 标准化流程",
        priority=2,
    ),
    
    # ===== LLM 推理优化 =====
    DistillProject(
        name="llama.cpp",
        github_url="https://github.com/ggerganov/llama.cpp",
        source_files=[
            "llama.cpp",
            "ggml/src/ggml.c",
        ],
        target_docs=[
            "knowledge/agent-ai/llamacpp-architecture-deep-dive.md",
        ],
        category="llm",
        core_value="C++ LLM 推理引擎 + 量化优化",
        priority=3,
    ),
    
    # ===== 向量数据库 =====
    DistillProject(
        name="Milvus",
        github_url="https://github.com/milvus-io/milvus",
        source_files=[
            "internal/proxy/proxy.go",
            "internal/rootcoord/root_coord.go",
            "pkg/storage/milvus_kvstore.go",
        ],
        target_docs=[
            "knowledge/agent-ai/milvus-architecture-deep-dive.md",
        ],
        category="database",
        core_value="向量搜索引擎 + 分布式架构",
        priority=3,
    ),
    
    # ===== 分布式计算框架 =====
    DistillProject(
        name="Ray",
        github_url="https://github.com/ray-project/ray",
        source_files=[
            "python/ray/_private/workers/workerd.py",
            "src/ray/core_worker/core_worker.py",
        ],
        target_docs=[
            "knowledge/bigdata/ray-architecture-deep-dive.md",
        ],
        category="runtime",
        core_value="分布式计算框架 + Python 原生支持",
        priority=4,
    ),
    
    # ===== 推理服务 =====
    DistillProject(
        name="Triton Inference Server",
        github_url="https://github.com/NVIDIA/triton-inference-server",
        source_files=[
            "src/servers/main.cc",
            "src/backends/tensorrt/tensorrt_backend.cc",
        ],
        target_docs=[
            "knowledge/agent-ai/triton-inference-server-deep-dive.md",
        ],
        category="llm",
        core_value="GPU 推理服务 + 多模型并发",
        priority=4,
    ),
    
    # ===== 消息队列 =====
    DistillProject(
        name="Pulsar",
        github_url="https://github.com/apache/pulsar",
        source_files=[
            "pulsar-broker/src/main/java/org/apache/pulsar/broker/PulsarService.java",
            "pulsar-client/src/main/java/org/apache/pulsar/client/impl/ConsumerImpl.java",
        ],
        target_docs=[
            "knowledge/messaging/pulsar-architecture-deep-dive.md",
        ],
        category="messaging",
        core_value="云原生消息队列 + 多租户隔离",
        priority=4,
    ),
    
    # ===== 流处理 =====
    DistillProject(
        name="Flink",
        github_url="https://github.com/apache/flink",
        source_files=[
            "flink-runtime/src/main/java/org/apache/flink/runtime/jobmanager/JobManagerProcess.java",
            "flink-streaming-java/src/main/java/org/apache/flink/streaming/api/Checkpointing.java",
        ],
        target_docs=[
            "knowledge/streaming/flink-architecture-deep-dive.md",
        ],
        category="runtime",
        core_value="流处理引擎 + Exactly-Once 语义",
        priority=5,
    ),
    
    # ===== 分布式数据库 =====
    DistillProject(
        name="TiDB",
        github_url="https://github.com/pingcap/tidb",
        source_files=[
            "pkg/session/session.go",
            "pkg/executor/executor.go",
            "pkg/planner/core/rule_decorrelate.go",
        ],
        target_docs=[
            "knowledge/database/tidb-session-deep-dive.md",
            "knowledge/database/tidb-executor-deep-dive.md",
            "knowledge/database/tidb-planner-deep-dive.md",
        ],
        category="database",
        core_value="HTAP 分布式数据库 + MySQL 兼容",
        priority=2,
    ),
    
    # ===== 分布式存储 =====
    DistillProject(
        name="TiKV",
        github_url="https://github.com/tikv/tikv",
        source_files=[
            "src/server/service/kv.rs",
            "src/server/raftstore/peer.rs",
            "components/raftstore/src/store/fsm/apply.rs",
        ],
        target_docs=[
            "knowledge/database/tikv-service-deep-dive.md",
            "knowledge/database/tikv-raft-deep-dive.md",
            "knowledge/database/tikv-apply-fsm-deep-dive.md",
        ],
        category="database",
        core_value="Raft 共识 + Lease 读优化",
        priority=3,
    ),
]


def get_projects_by_category(category: str) -> list[DistillProject]:
    """按分类获取项目"""
    return [p for p in DISTILL_PROJECTS if p.category == category and p.enabled]


def get_projects_by_priority(priority: int) -> list[DistillProject]:
    """按优先级获取项目"""
    return [p for p in DISTILL_PROJECTS if p.priority <= priority and p.enabled]


def get_all_projects() -> list[DistillProject]:
    """获取所有启用的项目"""
    return [p for p in DISTILL_PROJECTS if p.enabled]


if __name__ == "__main__":
    import json
    
    projects = get_all_projects()
    
    print(f"共配置 {len(projects)} 个知识蒸馏项目:\n")
    
    for i, project in enumerate(projects, 1):
        print(f"{i}. [{project.priority}] {project.name}")
        print(f"   GitHub: {project.github_url}")
        print(f"   分类: {project.category}")
        print(f"   核心: {project.core_value}")
        print()
