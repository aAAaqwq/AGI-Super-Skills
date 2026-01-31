/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */
import logger from 'debug';
import puppeteer, { Locator } from 'puppeteer';
import sinon from 'sinon';
import { McpContext } from '../src/McpContext.js';
import { McpResponse } from '../src/McpResponse.js';
import { stableIdSymbol } from '../src/PageCollector.js';
import { DevTools } from '../src/third_party/index.js';
export function getTextContent(content) {
    if (content.type === 'text') {
        return content.text;
    }
    throw new Error(`Expected text content but got ${content.type}`);
}
export function getImageContent(content) {
    if (content.type === 'image') {
        return { data: content.data, mimeType: content.mimeType };
    }
    throw new Error(`Expected image content but got ${content.type}`);
}
const browsers = new Map();
let context;
export async function withBrowser(cb, options = {}) {
    const launchOptions = {
        executablePath: process.env.PUPPETEER_EXECUTABLE_PATH,
        headless: !options.debug,
        defaultViewport: null,
        devtools: options.autoOpenDevTools ?? false,
        pipe: true,
        handleDevToolsAsPage: true,
    };
    const key = JSON.stringify(launchOptions);
    let browser = browsers.get(key);
    if (!browser) {
        browser = await puppeteer.launch(launchOptions);
        browsers.set(key, browser);
    }
    const newPage = await browser.newPage();
    // Close other pages.
    await Promise.all((await browser.pages()).map(async (page) => {
        if (page !== newPage) {
            await page.close();
        }
    }));
    await cb(browser, newPage);
}
export async function withMcpContext(cb, options = {}) {
    await withBrowser(async (browser) => {
        const response = new McpResponse();
        if (context) {
            context.dispose();
        }
        context = await McpContext.from(browser, logger('test'), {
            experimentalDevToolsDebugging: false,
        }, Locator);
        await cb(response, context);
    }, options);
}
export function getMockRequest(options = {}) {
    return {
        url() {
            return 'http://example.com';
        },
        method() {
            return options.method ?? 'GET';
        },
        fetchPostData() {
            return options.fetchPostData ?? Promise.reject();
        },
        hasPostData() {
            return options.hasPostData ?? false;
        },
        postData() {
            return options.postData;
        },
        response() {
            return options.response ?? null;
        },
        failure() {
            return options.failure?.() ?? null;
        },
        resourceType() {
            return options.resourceType ?? 'document';
        },
        headers() {
            return {
                'content-size': '10',
            };
        },
        redirectChain() {
            return [];
        },
        isNavigationRequest() {
            return options.navigationRequest ?? false;
        },
        frame() {
            return options.frame ?? {};
        },
        [stableIdSymbol]: options.stableId ?? 1,
    };
}
export function getMockResponse(options = {}) {
    return {
        status() {
            return options.status ?? 200;
        },
    };
}
export function html(strings, ...values) {
    const bodyContent = strings.reduce((acc, str, i) => {
        return acc + str + (values[i] || '');
    }, '');
    return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>My test page</title>
  </head>
  <body>
    ${bodyContent}
  </body>
</html>`;
}
export function stabilizeResponseOutput(text) {
    if (typeof text !== 'string') {
        throw new Error('Input must be string');
    }
    let output = text;
    const dateRegEx = /.{3}, \d{2} .{3} \d{4} \d{2}:\d{2}:\d{2} [A-Z]{3}/g;
    output = output.replaceAll(dateRegEx, '<long date>');
    const localhostRegEx = /localhost:\d{5}/g;
    output = output.replaceAll(localhostRegEx, 'localhost:<port>');
    const userAgentRegEx = /user-agent:.*\n/g;
    output = output.replaceAll(userAgentRegEx, 'user-agent:<user-agent>\n');
    const chUaRegEx = /sec-ch-ua:"Chromium";v="\d{3}"/g;
    output = output.replaceAll(chUaRegEx, 'sec-ch-ua:"Chromium";v="<version>"');
    // sec-ch-ua-platform:"Linux"
    const chUaPlatformRegEx = /sec-ch-ua-platform:"[a-zA-Z]*"/g;
    output = output.replaceAll(chUaPlatformRegEx, 'sec-ch-ua-platform:"<os>"');
    const savedSnapshot = /Saved snapshot to (.*)/g;
    output = output.replaceAll(savedSnapshot, 'Saved snapshot to <file>');
    return output;
}
export function getMockAggregatedIssue() {
    const mockAggregatedIssue = sinon.createStubInstance(DevTools.AggregatedIssue);
    mockAggregatedIssue.getAllIssues.returns([]);
    return mockAggregatedIssue;
}
export function mockListener() {
    const listeners = {};
    return {
        on(eventName, listener) {
            if (listeners[eventName]) {
                listeners[eventName].push(listener);
            }
            else {
                listeners[eventName] = [listener];
            }
        },
        off(_eventName, _listener) {
            // no-op
        },
        emit(eventName, data) {
            for (const listener of listeners[eventName] ?? []) {
                listener(data);
            }
        },
    };
}
export function getMockPage() {
    const mainFrame = {};
    const cdpSession = {
        ...mockListener(),
        send: () => {
            // no-op
        },
    };
    return {
        mainFrame() {
            return mainFrame;
        },
        ...mockListener(),
        // @ts-expect-error internal API.
        _client() {
            return cdpSession;
        },
    };
}
export function getMockBrowser() {
    const pages = [getMockPage()];
    return {
        pages() {
            return Promise.resolve(pages);
        },
        ...mockListener(),
    };
}
