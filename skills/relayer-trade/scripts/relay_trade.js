#!/usr/bin/env node
/**
 * relay_trade.js — Polymarket Relayer v2 Chain Trading
 * 
 * Bypasses CLOB geo-block by executing onchain transactions via Relayer v2.
 * Operations: buy(split), sell(merge/transfer), redeem, approve, ping
 * 
 * Usage:
 *   node relay_trade.js buy <conditionId> <amount_usdc> [--neg-risk]
 *   node relay_trade.js sell <conditionId> <amount> [--neg-risk]
 *   node relay_trade.js transfer <token_id> <to_address> <amount>
 *   node relay_trade.js redeem <conditionId> <yes_amount> <no_amount> [--neg-risk]
 *   node relay_trade.js approve-usdc
 *   node relay_trade.js approve-ctf <spender>
 *   node relay_trade.js check-redeemable
 *   node relay_trade.js ping
 */

const { RelayClient, RelayerTxType } = require('@polymarket/builder-relayer-client');
const { BuilderConfig } = require('@polymarket/builder-signing-sdk');
const { createWalletClient, http, encodeFunctionData, parseUnits, toHex, maxUint256 } = require('viem');
const { privateKeyToAccount } = require('viem/accounts');
const { polygon } = require('viem/chains');
const https = require('https');
const path = require('path');

// Load env
require('dotenv').config({ path: path.resolve(__dirname, '../../../.env.poly') });

// === Constants ===
const RELAYER_URL = 'https://relayer-v2.polymarket.com/';
const CHAIN_ID = 137;
const RPC_URL = 'https://polygon-bor-rpc.publicnode.com';

const USDC = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174';
const CTF = '0x4D97DCd97eC945f40cF65F87097ACe5EA0476045';
const CTF_EXCHANGE = '0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E';
const NEG_RISK_ADAPTER = '0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296';
const ZERO_BYTES32 = '0x0000000000000000000000000000000000000000000000000000000000000000';
const PARTITION_2 = [1n, 2n]; // Binary outcome: index 1=YES, index 2=NO

// === Init Client ===
function initClient() {
    const pk = process.env.POLY_PRIVATE_KEY;
    if (!pk) { console.error('❌ POLY_PRIVATE_KEY not set'); process.exit(1); }
    
    const account = privateKeyToAccount(pk);
    const wallet = createWalletClient({ account, chain: polygon, transport: http(RPC_URL) });
    
    const builderConfig = new BuilderConfig({
        localBuilderCreds: {
            key: process.env.POLY_BUILDER_API_KEY,
            secret: process.env.POLY_BUILDER_API_SECRET,
            passphrase: process.env.POLY_BUILDER_PASSPHRASE,
        },
    });
    
    return new RelayClient(RELAYER_URL, CHAIN_ID, wallet, builderConfig, RelayerTxType.PROXY);
}

// === Helper: fetch JSON ===
function fetchJSON(url) {
    return new Promise((resolve, reject) => {
        https.get(url, { headers: { 'Accept': 'application/json' } }, res => {
            let d = '';
            res.on('data', c => d += c);
            res.on('end', () => {
                try { resolve(JSON.parse(d)); }
                catch (e) { reject(new Error(`Invalid JSON from ${url}: ${d.slice(0, 200)}`)); }
            });
        }).on('error', reject);
    });
}

// === Helper: wait for tx ===
async function waitForTx(response) {
    const txId = response.transactionId;
    console.log(`TX ID: ${txId} | State: ${response.state || 'STATE_NEW'}`);
    
    try {
        const result = await response.wait();
        console.log('✅ SUCCESS:', JSON.stringify(result));
        return result;
    } catch (e) {
        console.log('❌ FAILED:', e.message?.substring(0, 300));
        return null;
    }
}

// === Commands ===

async function ping() {
    console.log('=== Relayer v2 Connectivity Test ===');
    const https = require('https');
    
    // 1. Relayer
    try {
        const r = await new Promise((resolve, reject) => {
            https.get(RELAYER_URL, res => {
                let d = ''; res.on('data', c => d += c);
                res.on('end', () => resolve({ status: res.statusCode, body: d }));
            }).on('error', reject);
        });
        console.log(`Relayer v2: ${r.status} ${r.body}`);
    } catch(e) { console.log(`Relayer v2: ❌ ${e.message}`); }
    
    // 2. Geoblock check
    try {
        const geo = await fetchJSON('https://polymarket.com/api/geoblock');
        console.log(`Geoblock: blocked=${geo.blocked} country=${geo.country} region=${geo.region} ip=${geo.ip}`);
    } catch(e) { console.log(`Geoblock: ❌ ${e.message}`); }
    
    // 3. Builder auth
    try {
        const client = initClient();
        const nonce = await client.getNonce(process.env.POLY_PROXY_WALLET, 'PROXY');
        console.log(`Builder Auth: ✅ nonce=${nonce.nonce}`);
    } catch(e) { console.log(`Builder Auth: ❌ ${e.message?.substring(0, 100)}`); }
    
    // 4. Proxy wallet
    console.log(`Proxy Wallet: ${process.env.POLY_PROXY_WALLET || 'NOT SET'}`);
    console.log(`EOA: ${process.env.POLY_PRIVATE_KEY ? 'SET' : 'NOT SET'}`);
}

async function approveUSDC(client) {
    console.log('=== Approve USDC.e for CTF ===');
    const tx = {
        to: USDC,
        data: encodeFunctionData({
            abi: [{ name: 'approve', type: 'function', inputs: [
                { name: 'spender', type: 'address' },
                { name: 'amount', type: 'uint256' },
            ], outputs: [{ type: 'bool' }] }],
            functionName: 'approve',
            args: [CTF, maxUint256],
        }),
        value: '0',
    };
    
    const response = await client.execute([tx], 'Approve USDC.e for CTF');
    return waitForTx(response);
}

async function approveCTF(client, spender) {
    console.log(`=== Approve CTF for ${spender} ===`);
    const tx = {
        to: CTF,
        data: encodeFunctionData({
            abi: [{ name: 'setApprovalForAll', type: 'function', inputs: [
                { name: 'operator', type: 'address' },
                { name: 'approved', type: 'bool' },
            ], outputs: [] }],
            functionName: 'setApprovalForAll',
            args: [spender, true],
        }),
        value: '0',
    };
    
    const response = await client.execute([tx], `Approve CTF for ${spender}`);
    return waitForTx(response);
}

async function buy(client, conditionId, amountUsdc, negRisk) {
    console.log(`=== BUY YES (split) ===`);
    console.log(`Condition: ${conditionId}`);
    console.log(`Amount: $${amountUsdc} USDC`);
    console.log(`NegRisk: ${negRisk || false}`);
    
    const amount = parseUnits(amountUsdc.toString(), 6); // 6 decimals for USDC
    
    const target = negRisk ? NEG_RISK_ADAPTER : CTF;
    const funcName = negRisk ? 'splitPosition' : 'splitPosition';
    
    if (negRisk) {
        // NegRisk: NegRiskAdapter.splitPosition(conditionId, amount)
        const tx = {
            to: NEG_RISK_ADAPTER,
            data: encodeFunctionData({
                abi: [{ name: 'splitPosition', type: 'function', inputs: [
                    { name: 'conditionId', type: 'bytes32' },
                    { name: 'amount', type: 'uint256' },
                ], outputs: [] }],
                functionName: 'splitPosition',
                args: [conditionId, amount],
            }),
            value: '0',
        };
        
        // Batch: approve + split
        const approveTx = {
            to: USDC,
            data: encodeFunctionData({
                abi: [{ name: 'approve', type: 'function', inputs: [
                    { name: 'spender', type: 'address' },
                    { name: 'amount', type: 'uint256' },
                ], outputs: [{ type: 'bool' }] }],
                functionName: 'approve',
                args: [NEG_RISK_ADAPTER, amount],
            }),
            value: '0',
        };
        
        console.log('Submitting: approve USDC + splitPosition (NegRisk)...');
        const response = await client.execute([approveTx, tx], `Buy YES via NegRisk split $${amountUsdc}`);
        return waitForTx(response);
    } else {
        // Standard: CTF.splitPosition(collateralToken, parentCollectionId, conditionId, partition, amount)
        const tx = {
            to: CTF,
            data: encodeFunctionData({
                abi: [{ name: 'splitPosition', type: 'function', inputs: [
                    { name: 'collateralToken', type: 'address' },
                    { name: 'parentCollectionId', type: 'bytes32' },
                    { name: 'conditionId', type: 'bytes32' },
                    { name: 'partition', type: 'uint256[]' },
                    { name: 'amount', type: 'uint256' },
                ], outputs: [] }],
                functionName: 'splitPosition',
                args: [USDC, ZERO_BYTES32, conditionId, PARTITION_2, amount],
            }),
            value: '0',
        };
        
        // Batch: approve + split
        const approveTx = {
            to: USDC,
            data: encodeFunctionData({
                abi: [{ name: 'approve', type: 'function', inputs: [
                    { name: 'spender', type: 'address' },
                    { name: 'amount', type: 'uint256' },
                ], outputs: [{ type: 'bool' }] }],
                functionName: 'approve',
                args: [CTF, amount],
            }),
            value: '0',
        };
        
        console.log('Submitting: approve USDC + splitPosition (CTF)...');
        const response = await client.execute([approveTx, tx], `Buy YES via CTF split $${amountUsdc}`);
        return waitForTx(response);
    }
}

async function sell(client, conditionId, amount, negRisk) {
    console.log(`=== SELL YES (merge) ===`);
    console.log(`Condition: ${conditionId}`);
    console.log(`Amount: ${amount} shares`);
    console.log(`⚠️ Requires holding both YES and NO tokens`);
    console.log(`NegRisk: ${negRisk || false}`);
    
    const rawAmount = parseUnits(amount.toString(), 6);
    
    if (negRisk) {
        // NegRisk: NegRiskAdapter.mergePositions(conditionId, [yesAmount, noAmount])
        const approveTx = {
            to: CTF,
            data: encodeFunctionData({
                abi: [{ name: 'setApprovalForAll', type: 'function', inputs: [
                    { name: 'operator', type: 'address' },
                    { name: 'approved', type: 'bool' },
                ], outputs: [] }],
                functionName: 'setApprovalForAll',
                args: [NEG_RISK_ADAPTER, true],
            }),
            value: '0',
        };
        
        const mergeTx = {
            to: NEG_RISK_ADAPTER,
            data: encodeFunctionData({
                abi: [{ name: 'mergePositions', type: 'function', inputs: [
                    { name: 'conditionId', type: 'bytes32' },
                    { name: 'amounts', type: 'uint256[]' },
                ], outputs: [] }],
                functionName: 'mergePositions',
                args: [conditionId, [rawAmount, rawAmount]],
            }),
            value: '0',
        };
        
        console.log('Submitting: approve CTF + mergePositions (NegRisk)...');
        const response = await client.execute([approveTx, mergeTx], `Sell YES via NegRisk merge ${amount}sh`);
        return waitForTx(response);
    } else {
        // Standard: CTF.mergePositions(collateralToken, parentCollectionId, conditionId, partition, amount)
        const mergeTx = {
            to: CTF,
            data: encodeFunctionData({
                abi: [{ name: 'mergePositions', type: 'function', inputs: [
                    { name: 'collateralToken', type: 'address' },
                    { name: 'parentCollectionId', type: 'bytes32' },
                    { name: 'conditionId', type: 'bytes32' },
                    { name: 'partition', type: 'uint256[]' },
                    { name: 'amount', type: 'uint256' },
                ], outputs: [] }],
                functionName: 'mergePositions',
                args: [USDC, ZERO_BYTES32, conditionId, PARTITION_2, rawAmount],
            }),
            value: '0',
        };
        
        console.log('Submitting: mergePositions (CTF)...');
        const response = await client.execute([mergeTx], `Sell YES via CTF merge ${amount}sh`);
        return waitForTx(response);
    }
}

async function transfer(client, tokenId, toAddress, amount) {
    console.log(`=== TRANSFER YES tokens ===`);
    console.log(`Token: ${tokenId}`);
    console.log(`To: ${toAddress}`);
    console.log(`Amount: ${amount} shares`);
    
    const rawAmount = parseUnits(amount.toString(), 6);
    
    const tx = {
        to: CTF,
        data: encodeFunctionData({
            abi: [{ name: 'safeTransferFrom', type: 'function', inputs: [
                { name: 'from', type: 'address' },
                { name: 'to', type: 'address' },
                { name: 'id', type: 'uint256' },
                { name: 'amount', type: 'uint256' },
                { name: 'data', type: 'bytes' },
            ], outputs: [] }],
            functionName: 'safeTransferFrom',
            args: [process.env.POLY_PROXY_WALLET, toAddress, BigInt(tokenId), rawAmount, '0x'],
        }),
        value: '0',
    };
    
    console.log('Submitting: safeTransferFrom...');
    const response = await client.execute([tx], `Transfer ${amount}sh YES to ${toAddress}`);
    return waitForTx(response);
}

async function redeem(client, conditionId, yesAmount, noAmount, negRisk) {
    console.log(`=== REDEEM ===`);
    console.log(`Condition: ${conditionId}`);
    console.log(`YES: ${yesAmount} | NO: ${noAmount}`);
    console.log(`NegRisk: ${negRisk || false}`);
    
    const rawYes = parseUnits(yesAmount.toString(), 6);
    const rawNo = parseUnits(noAmount.toString(), 6);
    
    if (negRisk) {
        // Step 1: Approve CTF for NegRiskAdapter
        console.log('Step 1: Approve CTF for NegRiskAdapter...');
        const approveTx = {
            to: CTF,
            data: encodeFunctionData({
                abi: [{ name: 'setApprovalForAll', type: 'function', inputs: [
                    { name: 'operator', type: 'address' },
                    { name: 'approved', type: 'bool' },
                ], outputs: [] }],
                functionName: 'setApprovalForAll',
                args: [NEG_RISK_ADAPTER, true],
            }),
            value: '0',
        };
        
        // Step 2: Redeem via NegRiskAdapter
        console.log('Step 2: Redeem via NegRiskAdapter...');
        const redeemTx = {
            to: NEG_RISK_ADAPTER,
            data: encodeFunctionData({
                abi: [{ name: 'redeemPositions', type: 'function', inputs: [
                    { name: '_conditionId', type: 'bytes32' },
                    { name: '_amounts', type: 'uint256[]' },
                ], outputs: [] }],
                functionName: 'redeemPositions',
                args: [conditionId, [rawYes, rawNo]],
            }),
            value: '0',
        };
        
        console.log('Submitting: approve + redeem (batch)...');
        const response = await client.execute([approveTx, redeemTx], `Redeem ${yesAmount} YES + ${noAmount} NO (NegRisk)`);
        return waitForTx(response);
    } else {
        // Standard: CTF.redeemPositions(collateralToken, parentCollectionId, conditionId, indexSets)
        const redeemTx = {
            to: CTF,
            data: encodeFunctionData({
                abi: [{ name: 'redeemPositions', type: 'function', inputs: [
                    { name: 'collateralToken', type: 'address' },
                    { name: 'parentCollectionId', type: 'bytes32' },
                    { name: 'conditionId', type: 'bytes32' },
                    { name: 'indexSets', type: 'uint256[]' },
                ], outputs: [] }],
                functionName: 'redeemPositions',
                args: [USDC, ZERO_BYTES32, conditionId, PARTITION_2],
            }),
            value: '0',
        };
        
        console.log('Submitting: redeemPositions (CTF)...');
        const response = await client.execute([redeemTx], `Redeem ${yesAmount} YES (CTF)`);
        return waitForTx(response);
    }
}

async function checkRedeemable() {
    console.log('=== Checking Redeemable Positions ===');
    const proxy = process.env.POLY_PROXY_WALLET;
    if (!proxy) { console.error('❌ POLY_PROXY_WALLET not set'); return; }
    
    try {
        const positions = await fetchJSON(`https://data-api.polymarket.com/positions?user=${proxy}`);
        const redeemable = positions.filter(p => p.redeemable);
        
        if (redeemable.length === 0) {
            console.log('No redeemable positions');
            return;
        }
        
        console.log(`Found ${redeemable.length} redeemable position(s):`);
        for (const p of redeemable) {
            console.log(`  📦 ${p.title?.substring(0, 60)}`);
            console.log(`     Size: ${p.size} | Condition: ${p.conditionId?.substring(0, 20)}...`);
            console.log(`     Outcome: ${p.outcome} | NegRisk: ${p.negRisk || false}`);
        }
    } catch(e) {
        console.error(`❌ ${e.message}`);
    }
}

// === Main ===
async function main() {
    const args = process.argv.slice(2);
    const cmd = args[0];
    
    if (!cmd || cmd === 'help' || cmd === '--help') {
        console.log(`
Usage: node relay_trade.js <command> [args...]

Commands:
  ping                          Test Relayer v2 connectivity
  approve-usdc                  Approve USDC.e for CTF (split)
  approve-ctf <spender>         Approve CTF for spender (redeem)
  buy <conditionId> <amount> [--neg-risk]  Buy YES via split
  sell <conditionId> <amount> [--neg-risk] Sell YES via merge
  transfer <tokenId> <to> <amt>          Transfer YES tokens
  redeem <condId> <yes> <no> [--neg-risk] Redeem settled positions
  check-redeemable              List redeemable positions
`);
        return;
    }
    
    // Commands that don't need client
    if (cmd === 'ping') { return ping(); }
    if (cmd === 'check-redeemable') { return checkRedeemable(); }
    
    const client = initClient();
    const negRisk = args.includes('--neg-risk');
    
    switch (cmd) {
        case 'approve-usdc':
            await approveUSDC(client);
            break;
        case 'approve-ctf':
            await approveCTF(client, args[1]);
            break;
        case 'buy':
            if (!args[1] || !args[2]) { console.error('Usage: buy <conditionId> <amount_usdc>'); return; }
            await buy(client, args[1], args[2], negRisk);
            break;
        case 'sell':
            if (!args[1] || !args[2]) { console.error('Usage: sell <conditionId> <amount>'); return; }
            await sell(client, args[1], args[2], negRisk);
            break;
        case 'transfer':
            if (!args[1] || !args[2] || !args[3]) { console.error('Usage: transfer <tokenId> <to_address> <amount>'); return; }
            await transfer(client, args[1], args[2], args[3]);
            break;
        case 'redeem':
            if (!args[1] || !args[2] || !args[3]) { console.error('Usage: redeem <conditionId> <yes_amount> <no_amount>'); return; }
            await redeem(client, args[1], args[2], args[3], negRisk);
            break;
        default:
            console.error(`Unknown command: ${cmd}`);
            process.exit(1);
    }
}

main().catch(e => {
    console.error('FATAL:', e.message);
    process.exit(1);
});
