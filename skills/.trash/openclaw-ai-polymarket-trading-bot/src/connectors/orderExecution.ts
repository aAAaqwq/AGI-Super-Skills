/**
 * Live order execution via Polymarket CLOB API.
 * Requires PRIVATE_KEY, CLOB_API_KEY, CLOB_SECRET, CLOB_PASS_PHRASE in env.
 */
import { ClobClient, Side, OrderType } from "@polymarket/clob-client";
import { Wallet } from "ethers";
import type { ApiKeyCreds } from "@polymarket/clob-client";
import { cfg } from "../config.js";

let _client: ClobClient | null = null;
let _publicClient: ClobClient | null = null;

function getPublicClient(): ClobClient {
  if (!_publicClient) {
    _publicClient = new ClobClient(cfg.clobApiUrl, cfg.clobChainId);
  }
  return _publicClient;
}

function getClient(): ClobClient {
  if (!_client) {
    if (!cfg.privateKey || !cfg.clobApiKey || !cfg.clobSecret || !cfg.clobPassphrase) {
      throw new Error(
        "Live trading disabled: set PRIVATE_KEY, CLOB_API_KEY, CLOB_SECRET, CLOB_PASS_PHRASE"
      );
    }
    const signer = new Wallet(cfg.privateKey);
    const creds: ApiKeyCreds = {
      key: cfg.clobApiKey,
      secret: cfg.clobSecret,
      passphrase: cfg.clobPassphrase
    };
    _client = new ClobClient(cfg.clobApiUrl, cfg.clobChainId, signer, creds);
  }
  return _client;
}

export type TokenIds = { yesTokenId: string; noTokenId: string };

/**
 * Resolve YES/NO token IDs for a market by condition ID (public, no auth).
 */
export async function getTokenIdsForCondition(conditionId: string): Promise<TokenIds | null> {
  try {
    const client = getPublicClient();
    const market = await client.getMarket(conditionId);
    const tokens = (market as { tokens?: Array<{ outcome: string; token_id: string }> }).tokens;
    if (!tokens || tokens.length < 2) return null;
    const yesToken = tokens.find((t) => /yes|up/i.test(t.outcome ?? ""));
    const noToken = tokens.find((t) => /no|down/i.test(t.outcome ?? ""));
    if (!yesToken || !noToken) return null;
    return { yesTokenId: yesToken.token_id, noTokenId: noToken.token_id };
  } catch {
    return null;
  }
}

export type PlaceOrderParams = {
  tokenId: string;
  side: "BUY" | "SELL";
  size: number; // shares for limit; for market BUY = USD amount, SELL = shares
  price: number; // 0..1, must match market tick size
  orderType?: "GTC" | "FOK" | "FAK";
};

export type PlaceOrderResult = {
  success: boolean;
  orderID?: string;
  status?: string;
  errorMsg?: string;
};

/**
 * Place a limit order (GTC) or market order (FOK/FAK).
 */
export async function placeOrder(params: PlaceOrderParams): Promise<PlaceOrderResult> {
  const client = getClient();
  const { tokenId, side, size, price, orderType = "GTC" } = params;
  const sideEnum = side === "BUY" ? Side.BUY : Side.SELL;

  try {
    if (orderType === "GTC") {
      const res = await client.createAndPostOrder(
        { tokenID: tokenId, price, size, side: sideEnum },
        undefined,
        OrderType.GTC
      );
      return {
        success: res.success ?? true,
        orderID: res.orderID,
        status: res.status
      };
    }
    // Market: FOK or FAK — BUY = amount in USD, SELL = amount in shares
    const marketType = orderType === "FAK" ? OrderType.FAK : OrderType.FOK;
    const marketOrder = await client.createAndPostMarketOrder(
      {
        tokenID: tokenId,
        side: sideEnum,
        amount: size,
        price
      },
      undefined,
      marketType
    );
    return {
      success: marketOrder.success ?? true,
      orderID: marketOrder.orderID,
      status: marketOrder.status
    };
  } catch (e: unknown) {
    const err = e as Error;
    return {
      success: false,
      errorMsg: err.message ?? String(e)
    };
  }
}

/**
 * Market buy: spend up to amountUsd at price at or better than priceLimit.
 */
export async function buy(
  tokenId: string,
  amountUsd: number,
  priceLimit: number
): Promise<PlaceOrderResult> {
  return placeOrder({
    tokenId,
    side: "BUY",
    size: amountUsd,
    price: priceLimit,
    orderType: "FOK"
  });
}

/**
 * Market sell: sell sizeShares at price at or better than priceLimit.
 */
export async function sell(
  tokenId: string,
  sizeShares: number,
  priceLimit: number
): Promise<PlaceOrderResult> {
  return placeOrder({
    tokenId,
    side: "SELL",
    size: sizeShares,
    price: priceLimit,
    orderType: "FOK"
  });
}
