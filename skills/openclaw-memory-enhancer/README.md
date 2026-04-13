# 🧠 OpenClaw Memory Enhancer

Edge-optimized RAG (Retrieval-Augmented Generation) memory system for [OpenClaw](https://openclaw.ai). 

**Make OpenClaw remember things across sessions.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-Compatible-green.svg)](https://openclaw.ai)

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **Semantic Search** | Find relevant memories by meaning, not just keywords |
| 💾 **Local Storage** | All data stays on your device - full privacy |
| 🚀 **Edge Optimized** | Memory usage < 10MB, runs on Jetson/Raspberry Pi |
| 📂 **Auto Load** | Automatically reads OpenClaw memory files |
| 🧠 **Smart Recall** | Automatically recalls context for conversations |
| 🔗 **Memory Graph** | Build connections between related memories |
| 🌍 **Multilingual** | Supports English and Chinese content |

## 📦 Installation

### Method 1: ClawHub (Recommended)

```bash
clawhub install openclaw-memory-enhancer
```

### Method 2: Git Clone

```bash
git clone https://github.com/henryfcb/openclaw-memory-enhancer.git \
  ~/.openclaw/skills/openclaw-memory-enhancer
```

### Method 3: Direct Download

```bash
cd ~/.openclaw/skills
wget https://github.com/henryfcb/openclaw-memory-enhancer/archive/refs/heads/main.zip
unzip main.zip
mv openclaw-memory-enhancer-main openclaw-memory-enhancer
```

## 🚀 Quick Start

### 1. Choose Your Version

| Version | Use Case | Memory | Dependencies |
|---------|----------|--------|--------------|
| **Edge** ⭐ | Jetson, Raspberry Pi, embedded devices | < 10MB | Python stdlib only |
| **Standard** | Desktop/server, maximum accuracy | 50-100MB | sentence-transformers |

### 2. Load Existing Memories

```bash
cd ~/.openclaw/skills/openclaw-memory-enhancer

# Edge version (recommended for most users)
python3 memory_enhancer_edge.py --load

# Or standard version (better accuracy)
pip install sentence-transformers numpy
python3 memory_enhancer.py --load
```

### 3. Search Memories

```bash
python3 memory_enhancer_edge.py --search "voice-call plugin configuration"
```

### 4. Add New Memory

```bash
python3 memory_enhancer_edge.py --add "User prefers dark mode interface"
```

## 💡 Usage Examples

### Python API

```python
from memory_enhancer_edge import MemoryEnhancerEdge

# Initialize
memory = MemoryEnhancerEdge()

# Load OpenClaw memories
memory.load_openclaw_memory()

# Search for relevant memories
results = memory.search_memory("AI trends report", top_k=3)
for r in results:
    print(f"[{r['similarity']:.2f}] {r['content'][:100]}...")

# Recall for conversation context
context = memory.recall_for_prompt("Help me check billing")
# Returns formatted memory context to enhance LLM prompts

# Add new memory
memory.add_memory(
    content="User prefers direct results when checking billing",
    source="chat",
    memory_type="preference"
)
```

### Integration with OpenClaw Agent

```python
# In your OpenClaw agent
from skills.openclaw_memory_enhancer.memory_enhancer_edge import MemoryEnhancerEdge

class EnhancedAgent:
    def __init__(self):
        self.memory = MemoryEnhancerEdge()
        self.memory.load_openclaw_memory()
    
    def process(self, user_input: str) -> str:
        # 1. Recall relevant memories
        memory_context = self.memory.recall_for_prompt(user_input)
        
        # 2. Enhance prompt with memories
        enhanced_prompt = f"""
{memory_context}

User: {user_input}
"""
        
        # 3. Call LLM with enhanced context
        response = call_llm(enhanced_prompt)
        
        return response
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│  User Input                                   │
└──────────────┬────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  MemoryEnhancer.recall_for_prompt()         │
│  ├── Keyword extraction                     │
│  ├── Vector similarity search               │
│  └── Return top-k relevant memories         │
└──────────────┬────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  Enhanced Prompt                            │
│  [Relevant Memories from History]           │
│  User: Current query                        │
└──────────────┬────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  LLM Response (with context)                │
└─────────────────────────────────────────────┘
```

## 📊 Performance

| Metric | Edge Version | Standard Version |
|--------|-------------|------------------|
| Memory Usage | < 10MB | 50-100MB |
| Query Latency | < 100ms | < 50ms |
| Dependencies | 0 | 2 (sentence-transformers, numpy) |
| Model Download | None | ~50MB |
| Vector Dimensions | 128 | 384 |
| Best For | Edge devices | Desktop/server |

## 🔒 Privacy & Security

- ✅ **100% Local**: No data leaves your device
- ✅ **No Cloud**: No external API calls
- ✅ **User Control**: You own and control all data
- ✅ **Transparent**: Open source, auditable code
- ✅ **No Tracking**: No analytics or telemetry

## 🛠️ Development

### Project Structure

```
openclaw-memory-enhancer/
├── README.md                      # This file
├── LICENSE                        # MIT License
├── SKILL.md                       # OpenClaw skill documentation
├── memory_enhancer_edge.py        # Edge optimized version (<10MB)
├── memory_enhancer.py             # Standard version (better accuracy)
└── knowledge_base.py              # Legacy knowledge base module
```

### Testing

```bash
# Load test
python3 memory_enhancer_edge.py --load

# Search test
python3 memory_enhancer_edge.py --search "test query"

# Show stats
python3 memory_enhancer_edge.py --stats

# Export memories
python3 memory_enhancer_edge.py --export
```

## 📝 CLI Reference

```bash
# Load OpenClaw memory files
python3 memory_enhancer_edge.py --load

# Search memories
python3 memory_enhancer_edge.py --search "query string"

# Add new memory
python3 memory_enhancer_edge.py --add "memory content"

# Export all memories to Markdown
python3 memory_enhancer_edge.py --export

# Show statistics
python3 memory_enhancer_edge.py --stats
```

## 🌟 Use Cases

| Scenario | How It Helps |
|----------|--------------|
| **Personal Assistant** | Remember user preferences across sessions |
| **Customer Support** | Build FAQ from chat history automatically |
| **Knowledge Management** | Create personal wiki from daily notes |
| **Development** | Remember project context and decisions |
| **Research** | Build knowledge graph from documents |

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/henryfcb/openclaw-memory-enhancer.git
cd openclaw-memory-enhancer

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies (for standard version)
pip install sentence-transformers numpy

# Run tests
python3 -m pytest tests/
```

## 📝 Changelog

### v1.0.0 (2025-02-22)
- Initial release
- Edge-optimized version with <10MB memory usage
- Semantic search with keyword + vector matching
- Automatic OpenClaw memory file loading
- Local storage for privacy protection
- Support for English and Chinese content

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built for [OpenClaw](https://openclaw.ai) ecosystem
- Inspired by memory systems in AI assistants
- Edge optimization for resource-constrained devices
- Thanks to the OpenClaw community for feedback

## 🔗 Links

- **GitHub**: https://github.com/henryfcb/openclaw-memory-enhancer
- **OpenClaw**: https://openclaw.ai
- **ClawHub**: https://clawhub.com

---

**Note**: This is not an official OpenClaw or Moonshot AI product. 
Requires user-provided OpenClaw workspace and API keys.

**Made with ❤️ for the OpenClaw community**