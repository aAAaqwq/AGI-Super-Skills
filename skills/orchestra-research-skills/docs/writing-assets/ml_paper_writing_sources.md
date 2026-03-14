# Comprehensive Source List: Building an ML Paper Writing Skill

This document compiles authoritative sources for creating a Claude skill that writes high-quality ML/AI papers for venues like ICLR, NeurIPS, and ICML.

---

## Part 1: Writing Philosophy & Guides from ML Researchers

### Primary Sources (Must-Read)

| Source | Author | URL | Key Value |
|--------|--------|-----|-----------|
| **Highly Opinionated Advice on How to Write ML Papers** | Neel Nanda | https://www.alignmentforum.org/posts/eJGptPbbFPZGLpjsp/highly-opinionated-advice-on-how-to-write-ml-papers | Core narrative philosophy, "what/why/so what" framework, figure-first approach |
| **How to Write ML Papers** | Sebastian Farquhar (DeepMind) | https://sebastianfarquhar.com/on-research/2024/11/04/how_to_write_ml_papers/ | 5-sentence abstract formula, structure templates, reader expectations |
| **A Survival Guide to a PhD** | Andrej Karpathy | http://karpathy.github.io/2016/09/07/phd/ | Paper structure recipe, importance of reviewing bad papers, contribution framing |
| **Heuristics for Scientific Writing (ML Perspective)** | Zachary Lipton (CMU) | https://www.approximatelycorrect.com/2018/01/29/heuristics-technical-scientific-writing-machine-learning-perspective/ | Snappy maxims for clear prose, vacuous intensifier warnings, section balance |
| **Advice for Authors** | Jacob Steinhardt (UC Berkeley) | https://jsteinhardt.stat.berkeley.edu/blog/advice-for-authors | Precision over brevity, consistent terminology, reader-centric writing |
| **Easy Paper Writing Tips** | Ethan Perez (Anthropic) | https://ethanperez.net/easy-paper-writing-tips/ | Practical micro-level tips, apostrophe unfolding, clarity tricks |

### Foundational Scientific Writing

| Source | Author | URL | Key Value |
|--------|--------|-----|-----------|
| **The Science of Scientific Writing** | Gopen & Swan | https://cseweb.ucsd.edu/~swanson/papers/science-of-writing.pdf | Topic/stress positions, old-before-new principle, sentence-level clarity |
| **Summary of Science of Scientific Writing** | Lawrence Crowl | https://www.crowl.org/Lawrence/writing/GopenSwan90.html | Condensed version of Gopen & Swan principles |

### Additional Researcher Perspectives

| Source | URL | Key Value |
|--------|-----|-----------|
| How To Write A Research Paper In Machine Learning | https://grigorisg9gr.github.io/machine%20learning/research%20paper/how-to-write-a-research-paper-in-machine-learning/ | Practical walkthrough |
| A Recipe for Training Neural Networks (Karpathy) | http://karpathy.github.io/2019/04/25/recipe/ | Debugging methodology that translates to paper structure |

---

## Part 2: Official Conference Guidelines

### NeurIPS

| Document | URL | Purpose |
|----------|-----|---------|
| **Paper Checklist Guidelines** | https://neurips.cc/public/guides/PaperChecklist | Mandatory checklist items, reproducibility requirements |
| **2025 Reviewer Guidelines** | https://neurips.cc/Conferences/2025/ReviewerGuidelines | What reviewers look for, scoring criteria |
| **Formatting Instructions** | https://arxiv.org/html/2505.10292v1 | LaTeX template, page limits, style requirements |

### ICML

| Document | URL | Purpose |
|----------|-----|---------|
| **Paper Guidelines** | https://icml.cc/Conferences/2024/PaperGuidelines | Submission requirements, ethics policy |
| **Style & Author Instructions** | https://icml.cc/Conferences/2022/StyleAuthorInstructions | Formatting specifications |
| **Reviewer Tutorial** | https://icml.cc/Conferences/2022/ReviewerTutorial | Evaluation criteria from reviewer perspective |
| **Reviewer Guidelines (2020)** | https://icml.cc/Conferences/2020/ReviewerGuidelines | Detailed review criteria |
| **ICML 2025 LaTeX Template** | https://www.overleaf.com/latex/templates/icml2025-template/dhxrkcgkvnkt | Official Overleaf template |

### ICLR

| Document | URL | Purpose |
|----------|-----|---------|
| **Author Guide 2026** | https://iclr.cc/Conferences/2026/AuthorGuide | Submission requirements, LLM disclosure policy |
| **LLM Disclosure Policy** | https://eu.36kr.com/en/p/3443306502428032 | NEW: Mandatory AI use disclosure (desk rejection if missing) |

---

## Part 3: Citation APIs & Tools (Hallucination Prevention)

### Primary APIs for Paper Search & Metadata

| API | Documentation URL | Key Features | Rate Limits |
|-----|-------------------|--------------|-------------|
| **Semantic Scholar API** | https://api.semanticscholar.org/api-docs/ | 214M papers, citation graphs, AI-trained search | 1 RPS with API key |
| **Semantic Scholar Tutorial** | https://www.semanticscholar.org/product/api/tutorial | Step-by-step usage guide | - |
| **CrossRef REST API** | https://www.crossref.org/documentation/retrieve-metadata/rest-api/ | DOI metadata, direct BibTeX via content negotiation | Polite pool with mailto |
| **arXiv API** | https://info.arxiv.org/help/api/basics.html | Preprint metadata, full-text access | 3-second delays |
| **OpenAlex API** | https://docs.openalex.org/api-entities/works | 240M+ works, CC0 license, open successor to MAG | 100K/day, 10 RPS |

### Python Libraries

| Library | Install | Documentation | Purpose |
|---------|---------|---------------|---------|
| `semanticscholar` | `pip install semanticscholar` | https://semanticscholar.readthedocs.io/ | Official-ish Python wrapper |
| `arxiv` | `pip install arxiv` | https://pypi.org/project/arxiv/ | arXiv search and download |
| `habanero` | `pip install habanero` | https://github.com/sckott/habanero | CrossRef Python client |

### BibTeX Retrieval Code Pattern

```python
import requests

def doi_to_bibtex(doi: str) -> str:
    """Get BibTeX directly from DOI via CrossRef content negotiation."""
    response = requests.get(
        f"https://doi.org/{doi}",
        headers={"Accept": "application/x-bibtex"}
    )
    response.raise_for_status()
    return response.text

# Example: Get verified BibTeX for "Attention Is All You Need"
bibtex = doi_to_bibtex("10.48550/arXiv.1706.03762")
```

### Citation Verification Tools

| Tool | URL | Purpose |
|------|-----|---------|
| **Citely** | https://citely.ai/citation-checker | Batch verification of AI-generated citations |
| **ReciteWorks** | https://reciteworks.com/ | Check in-text citations match reference list |

### LaTeX Citation Management

| Resource | URL | Key Info |
|----------|-----|----------|
| BibTeX vs BibLaTeX Guide | https://electricalvoice.com/latex-vs-bibtex-vs-biblatex/ | When to use which system |
| BibLaTeX Comprehensive Guide | https://latextutorial.net/latex-vs-bibtex-vs-biblatex/ | Modern citation management |

---

## Part 4: The Verified Citation Workflow

### Recommended Pipeline for AI-Assisted Writing

```
1. SEARCH: User specifies topic → Query Semantic Scholar API
   └─ Use paper/search endpoint with specific keywords
   
2. VERIFY EXISTENCE: For each candidate paper:
   └─ Confirm paper exists in 2+ sources (Semantic Scholar + CrossRef/arXiv)
   └─ Verify DOI resolves correctly
   
3. GET BIBTEX: Use DOI content negotiation
   └─ requests.get(f"https://doi.org/{doi}", headers={"Accept": "application/x-bibtex"})
   └─ NEVER generate BibTeX from memory - always fetch
   
4. VERIFY CLAIMS: Before citing paper for specific claim:
   └─ Retrieve paper abstract/full-text via Semantic Scholar
   └─ Confirm the attributed claim actually appears in source
   
5. BUILD BIBLIOGRAPHY:
   └─ Maintain .bib file with only verified entries
   └─ Use consistent citation keys (e.g., author_year_firstword)
```

### Why This Matters

From research on AI citation hallucination:
- ~40% of AI-generated citations contain errors (Enago Academy research)
- NeurIPS 2025 found 100+ hallucinated citations slipped through review
- Common errors: fabricated titles, wrong authors, non-existent papers with plausible metadata

---

## Part 5: Visualization & Formatting Resources

### Figure Creation

| Tool | URL | Purpose |
|------|-----|---------|
| **PlotNeuralNet** | https://github.com/HarisIqbal88/PlotNeuralNet | TikZ neural network diagrams |
| **SciencePlots** | https://github.com/garrettj403/SciencePlots | Publication-ready matplotlib styles |
| **Okabe-Ito Palette** | https://jfly.uni-koeln.de/color/ | Colorblind-safe color scheme |

### LaTeX Templates

| Venue | Template URL |
|-------|--------------|
| NeurIPS | https://neurips.cc/Conferences/2025/PaperInformation/StyleFiles |
| ICML | https://www.overleaf.com/latex/templates/icml2025-template/dhxrkcgkvnkt |
| ICLR | https://iclr.cc/Conferences/2026/AuthorGuide (links to template) |

---

## Part 6: Key Principles Summary (For Skill Encoding)

### From Neel Nanda
1. Paper = short, rigorous, evidence-based technical story with a takeaway readers care about
2. Spend equal time on: abstract, intro, figures, everything else
3. Every experiment must support a specific claim connected to contribution
4. "If you can't state your contribution in one sentence, you don't have a paper yet"

### From Karpathy
1. "The paper sells a single thing that was not obvious before"
2. Default structure: Intro → Related Work → Model → Experiments → Conclusions
3. Review bad papers to learn what NOT to do (binary classifier training)

### From Zachary Lipton
1. "If the first sentence can be pre-pended to any ML paper, delete it"
2. Figures should tell coherent story even if reader skips text
3. Sections should be balanced like bullets on slides
4. "provides *very* tight approximation" drips with insecurity → "provides tight approximation"

### From Sebastian Farquhar
1. Methods should start by page 2-3 maximum
2. Abstract formula: (1) What achieved, (2) Why hard/important, (3) How with keywords, (4-5) Evidence + best number
3. Introduction must have 2-4 bullet contribution list (max 1-2 lines each)

### From Gopen & Swan
1. Place emphasis at sentence ends (stress position)
2. Put context (old info) before new information
3. Keep subject and verb close together
4. One unit = one function (each paragraph = one point)

---

## Part 7: Additional Resources

### Hallucination & AI Writing Concerns

| Source | URL |
|--------|-----|
| AI Hallucinations in Research Citations | https://www.enago.com/academy/ai-hallucinations-research-citations/ |
| Hallucination in AI-Generated Writing (PMC) | https://pmc.ncbi.nlm.nih.gov/articles/PMC10726751/ |
| NeurIPS 2025 AI Hallucination Report | https://byteiota.com/neurips-2025-100-ai-hallucinations-slip-through-review/ |

### ML Conference Review System Analysis

| Source | URL |
|--------|-----|
| Position: ML Conferences Should Have Refutations Track | https://arxiv.org/html/2506.19882v1 |

---

## Usage Notes for Skill Development

1. **For paper structure**: Start with Nanda + Farquhar for high-level philosophy, use conference guidelines for specifics

2. **For writing style**: Combine Lipton's heuristics + Gopen & Swan's principles + Ethan Perez's micro-tips

3. **For citation workflow**: Implement Semantic Scholar → DOI verification → CrossRef BibTeX pipeline; NEVER generate citations from model memory

4. **For figures/tables**: Reference booktabs for tables, SciencePlots for figures, always use colorblind-safe palettes

5. **For reviewer simulation**: Study reviewer guidelines from all three venues to anticipate criticisms
