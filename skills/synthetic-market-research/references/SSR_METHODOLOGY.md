# SSR Methodology Reference

Based on: "LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings"
Authors: Ben F. Maier, Ulf Aslak, Lorenzo Fiaschi, Kostas Pappas, Thomas Wiecki (PyMC Labs)
Paper: https://arxiv.org/html/2510.08338v1
Package: https://github.com/pymc-labs/semantic-similarity-rating

## The Problem

When you ask an LLM to directly output a Likert scale number (1-5), the results are poor. LLMs compress responses into a narrow band (mean ~2.96, std 0.11 for GPT-4o), losing the variance and distribution shape that makes survey data useful.

## Three Approaches (from worst to best)

### 1. Direct Likert Rating (DLR) — Don't Use
Ask the LLM to output a single integer 1-5.
- KS similarity: 0.26-0.39
- Correlation attainment: ~80%
- **Problem**: Distributions too narrow, poor product discrimination

### 2. Follow-up Likert Rating (FLR) — OK
Two-step: LLM generates free-text, then a separate LLM instance rates the text on 1-5.
- KS similarity: 0.59-0.72
- Correlation attainment: 85-90%
- **Problem**: Still loses nuance by collapsing to a single number

### 3. Semantic Similarity Rating (SSR) — Use This
LLM generates free-text responses, which are mapped to *probability distributions* over Likert points using embedding cosine similarity. Preserves uncertainty and nuance.
- KS similarity: 0.80-0.88
- Correlation attainment: 90-92%
- **Advantage**: Outperforms even supervised ML (LightGBM: 64.6% correlation, 0.797 KS)

## How SSR Works

### Step 1: Generate Free-Text Responses
Prompt the LLM with a demographic persona and product concept. Ask for an honest, natural-language reaction — NOT a numeric rating.

### Step 2: Embed Responses and Reference Statements
Use an embedding model (default: `all-MiniLM-L6-v2`) to encode:
- Each LLM response
- Each reference statement (e.g., "I would definitely buy this")

### Step 3: Compute Cosine Similarity
Calculate cosine similarity between each response embedding and each reference statement embedding.

### Step 4: Convert to Probability Distribution
For each response:
1. Compute cosine similarity to all 5 reference statements
2. Subtract the minimum similarity (removes baseline)
3. Add epsilon regularization to the minimum position (prevents zeros)
4. Normalize to sum to 1.0

Result: a probability mass function (PMF) over 5 Likert points for each response.

### Step 5: Average Across Reference Sets
Use 4-6 different reference statement sets and average the resulting PMFs to reduce sensitivity to any single anchor formulation.

### Step 6: Aggregate
Average PMFs across all responses to get a survey-level distribution.

## Validation Results

| Metric | SSR (GPT-4o) | SSR (Gemini-2f) |
|--------|-------------|-----------------|
| KS Similarity | 0.88 | 0.80 |
| Correlation Attainment | 90% | 92% |
| Mean Purchase Intent | 3.77 +/- 0.31 | 3.51 +/- 0.42 |

Validated against **57 consumer research surveys** with **9,300 unique U.S. participants** (150-400 per survey).

## Demographics That Matter

### Replicated Well by LLMs
- **Age**: Both younger and older cohorts rate purchase intent lower than middle-aged. GPT-4o replicates this accurately.
- **Income Level**: Higher income → higher purchase intent. Both models replicate this.
- **Product Category**: Consistent cross-category patterns.
- **Price Tier**: Higher-tier products rated more positively (matches humans).

### Weak/Inconsistent Replication
- **Gender**: Weak influence in human data, inconsistent in synthetic.
- **Ethnicity**: Limited data, inconsistent replication.
- **Region/Location**: Weak influence, less consistent.

### Critical Finding
Removing ALL demographic info: distributional similarity goes UP (0.91 vs 0.80) but **correlation attainment collapses to 50%**. This means: basic distribution shape is achievable without personas, but meaningful product discrimination requires demographic conditioning.

## Package Usage

### Installation

```bash
pip install git+https://github.com/pymc-labs/semantic-similarity-rating.git
```

### Dependencies
- Python >= 3.10
- numpy, polars, scipy, sentence-transformers

### Code Example

```python
import polars as po
import numpy as np
from semantic_similarity_rating import ResponseRater

# Define reference statements (4-6 sets recommended)
df = po.DataFrame({
    "id": ["set1"] * 5 + ["set2"] * 5 + ["set3"] * 5 + ["set4"] * 5,
    "int_response": [1, 2, 3, 4, 5] * 4,
    "sentence": [
        # Set 1: Direct purchase intent
        "I would definitely not buy this",
        "I probably would not buy this",
        "I might or might not buy this",
        "I would probably buy this",
        "I would definitely buy this",
        # Set 2: Interest level
        "Not interested in purchasing at all",
        "Slightly interested in purchasing",
        "Moderately interested in purchasing",
        "Very interested in purchasing",
        "Extremely interested in purchasing",
        # Set 3: Appeal
        "This product has no appeal to me whatsoever",
        "This product has limited appeal to me",
        "This product has some appeal to me",
        "This product appeals to me quite a bit",
        "This product appeals to me tremendously",
        # Set 4: Consideration
        "I see no reason to consider buying this",
        "I might consider buying this in rare circumstances",
        "I could see myself buying this under the right conditions",
        "I would likely buy this if I needed something in this category",
        "I would actively seek this out and buy it",
    ],
})

# Initialize rater (downloads all-MiniLM-L6-v2 on first run)
rater = ResponseRater(df)

# LLM-generated free-text responses
llm_responses = [
    "This looks amazing, I'd buy it immediately for my team",
    "Not sure about this — seems overpriced for what it offers",
    "The safety features appeal to me but I need more info before deciding",
]

# Get PMF for each response using mean across all reference sets
pmfs = rater.get_response_pmfs(
    reference_set_id="mean",
    llm_responses=llm_responses,
    temperature=1.0,
    epsilon=0.0,
)
# pmfs.shape == (3, 5), each row sums to 1.0

# Get single survey-level PMF
survey_pmf = rater.get_survey_response_pmf(pmfs)

# Expected value (mean Likert score)
mean_score = np.dot(survey_pmf, [1, 2, 3, 4, 5])
print(f"Mean purchase intent: {mean_score:.2f}")
```

### Key API

- `ResponseRater(df_reference_sentences)` — Initialize with a Polars DataFrame containing columns: `id` (set identifier), `int_response` (1-5), `sentence` (reference text)
- `rater.get_response_pmfs(reference_set_id, llm_responses, temperature, epsilon)` — Convert responses to PMFs. Use `"mean"` for `reference_set_id` to average across all sets.
- `rater.get_survey_response_pmf(pmfs)` — Average PMFs across all responses
- `rater.available_reference_sets` — List available reference set IDs

## When to Use SSR

- Directional concept testing before spending on real panels
- Comparing multiple product variants quickly
- Early-stage pricing research
- Iterating on product descriptions/positioning
- Pre-screening concepts before formal research

## When NOT to Use SSR

- **Final validation** — always confirm with real users before major decisions
- **Niche products** without broad online discourse (LLM lacks training data)
- **Cultural/religious nuances** — LLMs don't reliably capture these
- **Products requiring physical experience** (taste, texture, fit)
- **Regulatory decisions** — synthetic data doesn't meet regulatory standards
- **Small, specialized professional audiences** — LLM personas are based on broad archetypes
