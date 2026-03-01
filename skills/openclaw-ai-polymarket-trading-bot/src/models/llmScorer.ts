import { FeatureVector } from "../types/index.js";

export class LlmScorer {
  constructor(
    private readonly apiKey?: string,
    private readonly baseUrl = "https://api.openai.com/v1",
    private readonly model = "gpt-4o-mini"
  ) {}

  async score(features: FeatureVector): Promise<number> {
    if (!this.apiKey) return 0; // neutral if not configured

    const prompt = `Score short-horizon UP probability bias in [-1,1].\nfeatures=${JSON.stringify(features)}`;

    const res = await fetch(`${this.baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.apiKey}`
      },
      body: JSON.stringify({
        model: this.model,
        temperature: 0,
        messages: [
          { role: "system", content: "Return ONLY a number between -1 and 1." },
          { role: "user", content: prompt }
        ]
      })
    });

    if (!res.ok) return 0;
    const data = await res.json() as any;
    const raw = Number((data.choices?.[0]?.message?.content ?? "0").trim());
    if (Number.isNaN(raw)) return 0;
    return Math.max(-1, Math.min(1, raw));
  }
}
