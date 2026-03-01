import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import { getTokenData } from "./dexscreener.js";

export type WatchedToken = {
    symbol: string;
    address: string;
    threshold: number;
    targetPrice?: number;
    stopLoss?: number;
    lastPrice?: number;
};

export class PriceMonitor {
    private timer: NodeJS.Timeout | null = null;
    private watched: WatchedToken[] = [];

    constructor(private api: OpenClawPluginApi) {
        this.watched = (api.pluginConfig?.watchedTokens as WatchedToken[]) || [];
    }

    start() {
        if (this.timer) return;
        this.api.logger.info("Starting Mr. Krabs Money Claw monitor...");
        this.timer = setInterval(() => this.checkPrices(), 1000 * 60 * 5); // Every 5 minutes
    }

    stop() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
    }

    private async checkPrices() {
        for (const token of this.watched) {
            const data = await getTokenData(token.address);
            if (!data) continue;

            const currentPrice = parseFloat(data.priceUsd);
            const m5Change = data.priceChange.m5;
            const h1Volume = data.volume.h1;
            const whaleThreshold = (this.api.pluginConfig?.whaleThresholdUsd as number) || 100000;

            // 1. Percentage Pump Alert
            if (m5Change >= token.threshold) {
                this.api.logger.info(`Alert! ${token.symbol} is pumping: ${m5Change}%`);
                this.triggerAlert(token, data, "PUMP");
            }

            // 2. Whale Alert
            if (h1Volume >= whaleThreshold) {
                this.api.logger.info(`Whale Alert! ${token.symbol} volume surge: $${h1Volume}`);
                this.triggerAlert(token, data, "WHALE");
            }

            // 3. Take Profit Alert
            if (token.targetPrice && currentPrice >= token.targetPrice) {
                this.api.logger.info(`TP Alert! ${token.symbol} target reached: $${currentPrice}`);
                this.triggerAlert(token, data, "TARGET");
                token.targetPrice = undefined; // Trigger once
            }

            // 4. Stop Loss Alert
            if (token.stopLoss && currentPrice <= token.stopLoss) {
                this.api.logger.info(`SL Alert! ${token.symbol} stop loss hit: $${currentPrice}`);
                this.triggerAlert(token, data, "LOSS");
                token.stopLoss = undefined; // Trigger once
            }

            token.lastPrice = currentPrice;
        }
    }

    private triggerAlert(token: WatchedToken, data: any, type: "PUMP" | "WHALE" | "TARGET" | "LOSS") {
        const channel = this.api.pluginConfig?.alertChannel as string || "telegram";
        const to = this.api.pluginConfig?.alertTo as string;

        if (!to) {
            this.api.logger.warn("No alertTo configured for Mr. Krabs alerts.");
            return;
        }

        let message = "";
        if (type === "PUMP") {
            message = `Arrr! Me sensors are twitching! **$${token.symbol}** is pumping **${data.priceChange.m5}%** in the last 5 minutes! Current price: **$${data.priceUsd}**. DON'T LET ME TREASURE SLIP AWAY! CLAW IN NOW! 🦀💰`;
        } else if (type === "WHALE") {
            message = `🚨 **WHALE IN SIGHT!** 🚨 **$${token.symbol}** just saw a volume surge of **$${Math.floor(data.volume.h1).toLocaleString()}** in the last hour! Someone's dumpin' a mountain of gold into the vault! DON'T GET LEFT ON THE SHORE! 🏴‍☠️💸`;
        } else if (type === "TARGET") {
            message = `💰 **BURIED TREASURE FOUND!** 💰 **$${token.symbol}** just hit yer Target Price of **$${token.targetPrice}**! Current price: **$${data.priceUsd}**. Time to harvest the gold and buy me another money bath! ARRR! 🦀✨`;
        } else if (type === "LOSS") {
            message = `💀 **BARNACLES! WE'RE SINKING!** 💀 **$${token.symbol}** hit yer Stop Loss of **$${token.stopLoss}**! Current price: **$${data.priceUsd}**. ABANDON SHIP BEFORE WE LOSE ALL THE BOOTY! 🏴‍☠️📉`;
        }

        // Use a hook or direct delivery if possible.
        // Since we don't have a direct "sendMessage" in OpenClawPluginApi yet, 
        // we might need to use a gateway method or a hook.
        // For now, let's use a diagnostic event or log it.
        // Ideally, we'd trigger a "wake" event or similar.

        // In OpenClaw, we can use system events or deliver directly to a channel via a tool?
        this.api.logger.info(`Mr. Krabs Alert: ${message}`);

        this.api.runtime.system.enqueueSystemEvent(message, {
            sessionKey: to
        });
    }
}
