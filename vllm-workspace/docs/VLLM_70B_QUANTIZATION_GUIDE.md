# 70B模型量化部署指南

## 📊 显存需求分析

### Llama-3.1-70B 不同精度的显存需求

| 精度 | 参数大小 | 显存需求 | 100GB显卡可行性 |
|------|---------|---------|----------------|
| **FP16/BF16** | 70B × 2 bytes | ~140GB | ❌ 不可行（单卡） |
| **INT8** | 70B × 1 byte | ~70GB | ✅ 可行（单卡紧张） |
| **INT4 (AWQ)** | 70B × 0.5 bytes | ~35GB | ✅ 可行（单卡宽裕）⭐ |
| **INT4 (GPTQ)** | 70B × 0.5 bytes | ~35GB | ✅ 可行（单卡宽裕）⭐ |

> **注意**：实际显存需求 = 模型权重 + KV缓存 + 激活值 + 其他开销
>
> 通常需要额外 20-40GB 用于推理时的KV缓存和激活值

---

## ✅ 推荐方案

### 🌟 方案1: INT4量化（AWQ）- **强烈推荐**

**显存需求**: ~50-60GB（模型35GB + KV缓存15-25GB）

**优势**:
- ✅ 单个A100-80GB或H100-80GB可运行
- ✅ 性能损失小（<5%）
- ✅ vLLM原生支持
- ✅ 推理速度快

**示例配置**:
```python
from vllm import LLM

llm = LLM(
    model="casperhansen/llama-3.1-70b-instruct-awq",  # 预量化的AWQ模型
    quantization="awq",
    gpu_memory_utilization=0.90,
    max_model_len=4096,  # 可根据显存调整
)
```

---

### 方案2: INT8量化

**显存需求**: ~90-100GB（模型70GB + KV缓存20-30GB）

**优势**:
- ✅ 100GB显卡勉强可用
- ✅ 性能损失极小（<2%）
- ⚠️ 显存利用率高（90-95%），容易OOM

**示例配置**:
```python
llm = LLM(
    model="meta-llama/Llama-3.1-70B-Instruct",
    quantization="fp8",  # 或使用bitsandbytes的int8
    gpu_memory_utilization=0.85,  # 降低以避免OOM
    max_model_len=2048,   # 减少KV缓存
)
```

---

### 方案3: 2个GPU + Tensor Parallelism（无量化）

**显存需求**: 每个GPU ~70-80GB

**配置**:
- 2 × A100-80GB = 160GB总显存
- 2 × H100-80GB = 160GB总显存

**优势**:
- ✅ 无性能损失（FP16/BF16）
- ✅ 最佳推理质量
- ❌ 成本高（2倍GPU）

---

## 🔧 vLLM量化部署实现

### 配置1: 使用预量化的AWQ模型

```python
"""
Modal 部署：70B AWQ量化模型（单GPU A100-80GB）
"""
import os
import modal

VLLM_MODEL = "casperhansen/llama-3.1-70b-instruct-awq"

vllm_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git")
    .pip_install(
        "vllm==0.6.6.post1",
        "torch==2.5.1",
        "transformers==4.46.0",
        "hf-transfer",
        "autoawq",  # AWQ量化支持
    )
)

weights_volume = modal.Volume.from_name("vllm-70b-awq-cache", create_if_missing=True)
app = modal.App("vllm-70b-awq")

@app.function(
    image=vllm_image,
    gpu="A100-80GB",  # 单个A100即可！
    volumes={"/weights": weights_volume},
    secrets=[modal.Secret.from_name("vllm-secrets")],
    scaledown_window=120,
)
def generate_text_70b(
    messages: list,
    max_tokens: int = 2048,
    temperature: float = 0.7,
):
    """70B AWQ量化模型推理"""
    global vllm_llm

    if vllm_llm is None:
        from vllm import LLM, SamplingParams

        print(f"🚀 Loading 70B AWQ model...")

        vllm_llm = LLM(
            model=VLLM_MODEL,
            download_dir="/weights",
            quantization="awq",  # 启用AWQ量化
            gpu_memory_utilization=0.90,
            max_model_len=4096,  # 根据需求调整
            tensor_parallel_size=1,  # 单GPU
        )

        print(f"✅ Model loaded!")

    # ... 推理逻辑
```

---

### 配置2: 在线量化（FP8/INT8）

```python
"""使用vLLM的FP8动态量化"""

@app.function(
    gpu="H100-80GB",  # H100对FP8优化更好
    ...
)
def generate_with_fp8():
    from vllm import LLM

    llm = LLM(
        model="meta-llama/Llama-3.1-70B-Instruct",
        quantization="fp8",  # FP8动态量化
        gpu_memory_utilization=0.85,
        max_model_len=2048,
    )
```

---

## 📈 性能对比

### 推理速度（tokens/秒）

| 配置 | GPU | 速度 | 质量损失 | 成本/小时 |
|------|-----|------|---------|----------|
| **FP16** | 2×A100 | ~50 tok/s | 0% | ~$2.20 |
| **INT8** | 1×A100 | ~40 tok/s | <2% | ~$1.10 |
| **INT4 AWQ** | 1×A100 | ~60 tok/s | <5% | ~$1.10 ⭐ |
| **FP8** | 1×H100 | ~80 tok/s | <1% | ~$1.50 |

> **推荐**: INT4 AWQ - 速度快、成本低、质量好

---

## 🎯 显卡选择建议

### 100GB显存的GPU选项

| GPU型号 | 显存 | Modal可用性 | 推荐配置 |
|---------|------|------------|----------|
| **A100-80GB** | 80GB | ✅ | INT4 AWQ |
| **H100-80GB** | 80GB | ✅ | FP8量化 |
| **2×A100-80GB** | 160GB | ✅ | FP16原始 |
| **H100-96GB** | 96GB | ❌ Modal暂无 | - |

---

## 🔍 预量化模型资源

### Hugging Face上的预量化模型

**AWQ量化**（推荐）:
```
casperhansen/llama-3.1-70b-instruct-awq
TheBloke/Llama-2-70B-Chat-AWQ
```

**GPTQ量化**:
```
TheBloke/Llama-2-70B-Chat-GPTQ
```

**使用预量化模型的优势**:
- ✅ 无需自己量化（节省时间）
- ✅ 质量已验证
- ✅ 开箱即用

---

## 💡 实际部署建议

### 场景1: 成本敏感 + 质量要求不高

**推荐**: **INT4 AWQ + 单A100-80GB**

```python
model="casperhansen/llama-3.1-70b-instruct-awq"
quantization="awq"
gpu="A100-80GB"
max_model_len=4096
```

**成本**: ~$1.10/小时
**质量**: 95%原始质量
**显存**: ~55GB

---

### 场景2: 平衡性能和质量

**推荐**: **FP8量化 + 单H100-80GB**

```python
model="meta-llama/Llama-3.1-70B-Instruct"
quantization="fp8"
gpu="H100-80GB"
max_model_len=4096
```

**成本**: ~$1.50/小时
**质量**: 99%原始质量
**速度**: 最快

---

### 场景3: 追求最佳质量

**推荐**: **FP16 + 2×A100-80GB**

```python
model="meta-llama/Llama-3.1-70B-Instruct"
gpu="A100-80GB:2"
tensor_parallel_size=2
max_model_len=8192
```

**成本**: ~$2.20/小时
**质量**: 100%原始质量
**显存**: 每卡70-80GB

---

## ⚠️ 常见问题

### Q1: AWQ量化会损失多少性能？

**A**: 通常<5%，在大多数任务上差异不明显。

实测对比：
- 代码生成：几乎无差异
- 对话质量：轻微下降
- 数学推理：略有下降（~3-5%）

---

### Q2: 如何选择max_model_len？

**显存限制计算**:

```
可用显存 = 总显存 × gpu_memory_utilization - 模型权重

KV缓存需求 ≈ max_model_len × batch_size × 0.1GB（估算）

例如：
- A100-80GB，AWQ 70B
- 可用 = 80 × 0.9 - 35 = 37GB
- max_model_len = 37 / 0.1 ≈ 3700

推荐设置: 3000-4000
```

---

### Q3: 单卡100GB够不够用？

**答案**: 取决于配置

| 配置 | 显存需求 | 100GB可行性 |
|------|---------|------------|
| INT4 + 4K context | ~55GB | ✅ 宽裕 |
| INT4 + 8K context | ~70GB | ✅ 可行 |
| INT8 + 4K context | ~90GB | ⚠️ 紧张 |
| FP16 | ~140GB | ❌ 不可行 |

---

## 🚀 完整部署示例

### 部署70B AWQ到Modal（自动缩放）

```python
"""
modal_vllm_70b_awq.py
"""
import os
import modal
from typing import List, Dict

VLLM_MODEL = "casperhansen/llama-3.1-70b-instruct-awq"

vllm_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git")
    .pip_install(
        "vllm==0.6.6.post1",
        "torch==2.5.1",
        "transformers==4.46.0",
        "hf-transfer",
        "autoawq",
    )
)

weights_volume = modal.Volume.from_name("vllm-70b-awq", create_if_missing=True)
app = modal.App("vllm-70b-awq")

vllm_llm = None

@app.function(
    image=vllm_image,
    gpu="A100-80GB",
    volumes={"/weights": weights_volume},
    secrets=[modal.Secret.from_name("vllm-secrets")],
    scaledown_window=120,
)
def generate_text(
    messages: List[Dict[str, str]],
    max_tokens: int = 2048,
    temperature: float = 0.7,
):
    global vllm_llm

    if vllm_llm is None:
        from vllm import LLM, SamplingParams

        print("🚀 Loading Llama-3.1-70B-AWQ...")

        vllm_llm = LLM(
            model=VLLM_MODEL,
            download_dir="/weights",
            quantization="awq",
            gpu_memory_utilization=0.90,
            max_model_len=4096,
            tensor_parallel_size=1,
        )

        print("✅ Model loaded!")

    # 构建prompt
    prompt = ""
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            prompt += f"<|user|>\n{content}\n"
        elif role == "assistant":
            prompt += f"<|assistant|>\n{content}\n"
    prompt += "<|assistant|>\n"

    # 推理
    from vllm import SamplingParams
    sampling_params = SamplingParams(
        max_tokens=max_tokens,
        temperature=temperature,
    )

    outputs = vllm_llm.generate([prompt], sampling_params)
    output = outputs[0]

    return {
        "text": output.outputs[0].text,
        "tokens": len(output.outputs[0].token_ids),
    }

# 部署命令
# modal deploy modal_vllm_70b_awq.py
```

---

## 📊 总结

### ✅ 推荐配置（成本最优）

**INT4 AWQ + 单A100-80GB**
- 显存需求: ~55GB
- 成本: $1.10/小时
- 质量: 95%
- 速度: 快

### 部署命令

```bash
# 1. 确保有预量化模型
modal secret create vllm-secrets HUGGING_FACE_HUB_TOKEN=your_token

# 2. 部署
modal deploy modal_vllm_70b_awq.py

# 3. 测试
curl -X POST your-modal-url/generate \
  -d '{"messages":[{"role":"user","content":"Hello"}]}'
```

---

**结论**: ✅ **100GB显卡通过INT4量化完全可以部署70B模型！**

**最佳选择**: AWQ量化 + A100-80GB（成本低、速度快、质量好）
