/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */
import { mapIssueToMessageObject } from './DevtoolsUtils.js';
import { formatConsoleEventShort, formatConsoleEventVerbose, } from './formatters/consoleFormatter.js';
import { getFormattedHeaderValue, getFormattedResponseBody, getFormattedRequestBody, getShortDescriptionForRequest, getStatusFromRequest, } from './formatters/networkFormatter.js';
import { formatSnapshotNode } from './formatters/snapshotFormatter.js';
import { DevTools } from './third_party/index.js';
import { handleDialog } from './tools/pages.js';
import { paginate } from './utils/pagination.js';
export class McpResponse {
    #includePages = false;
    #snapshotParams;
    #attachedNetworkRequestId;
    #attachedConsoleMessageId;
    #textResponseLines = [];
    #images = [];
    #networkRequestsOptions;
    #consoleDataOptions;
    #devToolsData;
    attachDevToolsData(data) {
        this.#devToolsData = data;
    }
    setIncludePages(value) {
        this.#includePages = value;
    }
    includeSnapshot(params) {
        this.#snapshotParams = params ?? {
            verbose: false,
        };
    }
    setIncludeNetworkRequests(value, options) {
        if (!value) {
            this.#networkRequestsOptions = undefined;
            return;
        }
        this.#networkRequestsOptions = {
            include: value,
            pagination: options?.pageSize || options?.pageIdx
                ? {
                    pageSize: options.pageSize,
                    pageIdx: options.pageIdx,
                }
                : undefined,
            resourceTypes: options?.resourceTypes,
            includePreservedRequests: options?.includePreservedRequests,
            networkRequestIdInDevToolsUI: options?.networkRequestIdInDevToolsUI,
        };
    }
    setIncludeConsoleData(value, options) {
        if (!value) {
            this.#consoleDataOptions = undefined;
            return;
        }
        this.#consoleDataOptions = {
            include: value,
            pagination: options?.pageSize || options?.pageIdx
                ? {
                    pageSize: options.pageSize,
                    pageIdx: options.pageIdx,
                }
                : undefined,
            types: options?.types,
            includePreservedMessages: options?.includePreservedMessages,
        };
    }
    attachNetworkRequest(reqid) {
        this.#attachedNetworkRequestId = reqid;
    }
    attachConsoleMessage(msgid) {
        this.#attachedConsoleMessageId = msgid;
    }
    get includePages() {
        return this.#includePages;
    }
    get includeNetworkRequests() {
        return this.#networkRequestsOptions?.include ?? false;
    }
    get includeConsoleData() {
        return this.#consoleDataOptions?.include ?? false;
    }
    get attachedNetworkRequestId() {
        return this.#attachedNetworkRequestId;
    }
    get networkRequestsPageIdx() {
        return this.#networkRequestsOptions?.pagination?.pageIdx;
    }
    get consoleMessagesPageIdx() {
        return this.#consoleDataOptions?.pagination?.pageIdx;
    }
    get consoleMessagesTypes() {
        return this.#consoleDataOptions?.types;
    }
    appendResponseLine(value) {
        this.#textResponseLines.push(value);
    }
    attachImage(value) {
        this.#images.push(value);
    }
    get responseLines() {
        return this.#textResponseLines;
    }
    get images() {
        return this.#images;
    }
    get snapshotParams() {
        return this.#snapshotParams;
    }
    async handle(toolName, context) {
        if (this.#includePages) {
            await context.createPagesSnapshot();
        }
        let formattedSnapshot;
        if (this.#snapshotParams) {
            await context.createTextSnapshot(this.#snapshotParams.verbose, this.#devToolsData);
            const snapshot = context.getTextSnapshot();
            if (snapshot) {
                if (this.#snapshotParams.filePath) {
                    await context.saveFile(new TextEncoder().encode(formatSnapshotNode(snapshot.root, snapshot)), this.#snapshotParams.filePath);
                    formattedSnapshot = `Saved snapshot to ${this.#snapshotParams.filePath}.`;
                }
                else {
                    formattedSnapshot = formatSnapshotNode(snapshot.root, snapshot);
                }
            }
        }
        const bodies = {};
        if (this.#attachedNetworkRequestId) {
            const request = context.getNetworkRequestById(this.#attachedNetworkRequestId);
            bodies.requestBody = await getFormattedRequestBody(request);
            const response = request.response();
            if (response) {
                bodies.responseBody = await getFormattedResponseBody(response);
            }
        }
        let consoleData;
        if (this.#attachedConsoleMessageId) {
            const message = context.getConsoleMessageById(this.#attachedConsoleMessageId);
            const consoleMessageStableId = this.#attachedConsoleMessageId;
            if ('args' in message) {
                const consoleMessage = message;
                consoleData = {
                    consoleMessageStableId,
                    type: consoleMessage.type(),
                    message: consoleMessage.text(),
                    args: await Promise.all(consoleMessage.args().map(async (arg) => {
                        const stringArg = await arg.jsonValue().catch(() => {
                            // Ignore errors.
                        });
                        return typeof stringArg === 'object'
                            ? JSON.stringify(stringArg)
                            : String(stringArg);
                    })),
                };
            }
            else if (message instanceof DevTools.AggregatedIssue) {
                const mappedIssueMessage = mapIssueToMessageObject(message);
                if (!mappedIssueMessage)
                    throw new Error("Can't provide detals for the msgid " + consoleMessageStableId);
                consoleData = {
                    consoleMessageStableId,
                    ...mappedIssueMessage,
                };
            }
            else {
                consoleData = {
                    consoleMessageStableId,
                    type: 'error',
                    message: message.message,
                    args: [],
                };
            }
        }
        let consoleListData;
        if (this.#consoleDataOptions?.include) {
            let messages = context.getConsoleData(this.#consoleDataOptions.includePreservedMessages);
            if (this.#consoleDataOptions.types?.length) {
                const normalizedTypes = new Set(this.#consoleDataOptions.types);
                messages = messages.filter(message => {
                    if ('type' in message) {
                        return normalizedTypes.has(message.type());
                    }
                    if (message instanceof DevTools.AggregatedIssue) {
                        return normalizedTypes.has('issue');
                    }
                    return normalizedTypes.has('error');
                });
            }
            consoleListData = (await Promise.all(messages.map(async (item) => {
                const consoleMessageStableId = context.getConsoleMessageStableId(item);
                if ('args' in item) {
                    const consoleMessage = item;
                    return {
                        consoleMessageStableId,
                        type: consoleMessage.type(),
                        message: consoleMessage.text(),
                        args: await Promise.all(consoleMessage.args().map(async (arg) => {
                            const stringArg = await arg.jsonValue().catch(() => {
                                // Ignore errors.
                            });
                            return typeof stringArg === 'object'
                                ? JSON.stringify(stringArg)
                                : String(stringArg);
                        })),
                    };
                }
                if (item instanceof DevTools.AggregatedIssue) {
                    const mappedIssueMessage = mapIssueToMessageObject(item);
                    if (!mappedIssueMessage)
                        return null;
                    return {
                        consoleMessageStableId,
                        ...mappedIssueMessage,
                    };
                }
                return {
                    consoleMessageStableId,
                    type: 'error',
                    message: item.message,
                    args: [],
                };
            }))).filter(item => item !== null);
        }
        return this.format(toolName, context, {
            bodies,
            consoleData,
            consoleListData,
            formattedSnapshot,
        });
    }
    format(toolName, context, data) {
        const response = [`# ${toolName} response`];
        for (const line of this.#textResponseLines) {
            response.push(line);
        }
        const networkConditions = context.getNetworkConditions();
        if (networkConditions) {
            response.push(`## Network emulation`);
            response.push(`Emulating: ${networkConditions}`);
            response.push(`Default navigation timeout set to ${context.getNavigationTimeout()} ms`);
        }
        const cpuThrottlingRate = context.getCpuThrottlingRate();
        if (cpuThrottlingRate > 1) {
            response.push(`## CPU emulation`);
            response.push(`Emulating: ${cpuThrottlingRate}x slowdown`);
        }
        const dialog = context.getDialog();
        if (dialog) {
            const defaultValueIfNeeded = dialog.type() === 'prompt'
                ? ` (default value: "${dialog.defaultValue()}")`
                : '';
            response.push(`# Open dialog
${dialog.type()}: ${dialog.message()}${defaultValueIfNeeded}.
Call ${handleDialog.name} to handle it before continuing.`);
        }
        if (this.#includePages) {
            const parts = [`## Pages`];
            let idx = 0;
            for (const page of context.getPages()) {
                parts.push(`${idx}: ${page.url()}${context.isPageSelected(page) ? ' [selected]' : ''}`);
                idx++;
            }
            response.push(...parts);
        }
        if (data.formattedSnapshot) {
            response.push('## Latest page snapshot');
            response.push(data.formattedSnapshot);
        }
        response.push(...this.#formatNetworkRequestData(context, data.bodies));
        response.push(...this.#formatConsoleData(context, data.consoleData));
        if (this.#networkRequestsOptions?.include) {
            let requests = context.getNetworkRequests(this.#networkRequestsOptions?.includePreservedRequests);
            // Apply resource type filtering if specified
            if (this.#networkRequestsOptions.resourceTypes?.length) {
                const normalizedTypes = new Set(this.#networkRequestsOptions.resourceTypes);
                requests = requests.filter(request => {
                    const type = request.resourceType();
                    return normalizedTypes.has(type);
                });
            }
            response.push('## Network requests');
            if (requests.length) {
                const data = this.#dataWithPagination(requests, this.#networkRequestsOptions.pagination);
                response.push(...data.info);
                for (const request of data.items) {
                    response.push(getShortDescriptionForRequest(request, context.getNetworkRequestStableId(request), context.getNetworkRequestStableId(request) ===
                        this.#networkRequestsOptions?.networkRequestIdInDevToolsUI));
                }
            }
            else {
                response.push('No requests found.');
            }
        }
        if (this.#consoleDataOptions?.include) {
            const messages = data.consoleListData ?? [];
            response.push('## Console messages');
            if (messages.length) {
                const data = this.#dataWithPagination(messages, this.#consoleDataOptions.pagination);
                response.push(...data.info);
                response.push(...data.items.map(message => formatConsoleEventShort(message)));
            }
            else {
                response.push('<no console messages found>');
            }
        }
        const text = {
            type: 'text',
            text: response.join('\n'),
        };
        const images = this.#images.map(imageData => {
            return {
                type: 'image',
                ...imageData,
            };
        });
        return [text, ...images];
    }
    #dataWithPagination(data, pagination) {
        const response = [];
        const paginationResult = paginate(data, pagination);
        if (paginationResult.invalidPage) {
            response.push('Invalid page number provided. Showing first page.');
        }
        const { startIndex, endIndex, currentPage, totalPages } = paginationResult;
        response.push(`Showing ${startIndex + 1}-${endIndex} of ${data.length} (Page ${currentPage + 1} of ${totalPages}).`);
        if (pagination) {
            if (paginationResult.hasNextPage) {
                response.push(`Next page: ${currentPage + 1}`);
            }
            if (paginationResult.hasPreviousPage) {
                response.push(`Previous page: ${currentPage - 1}`);
            }
        }
        return {
            info: response,
            items: paginationResult.items,
        };
    }
    #formatConsoleData(context, data) {
        const response = [];
        if (!data) {
            return response;
        }
        response.push(formatConsoleEventVerbose(data, context));
        return response;
    }
    #formatNetworkRequestData(context, data) {
        const response = [];
        const id = this.#attachedNetworkRequestId;
        if (!id) {
            return response;
        }
        const httpRequest = context.getNetworkRequestById(id);
        response.push(`## Request ${httpRequest.url()}`);
        response.push(`Status:  ${getStatusFromRequest(httpRequest)}`);
        response.push(`### Request Headers`);
        for (const line of getFormattedHeaderValue(httpRequest.headers())) {
            response.push(line);
        }
        if (data.requestBody) {
            response.push(`### Request Body`);
            response.push(data.requestBody);
        }
        const httpResponse = httpRequest.response();
        if (httpResponse) {
            response.push(`### Response Headers`);
            for (const line of getFormattedHeaderValue(httpResponse.headers())) {
                response.push(line);
            }
        }
        if (data.responseBody) {
            response.push(`### Response Body`);
            response.push(data.responseBody);
        }
        const httpFailure = httpRequest.failure();
        if (httpFailure) {
            response.push(`### Request failed with`);
            response.push(httpFailure.errorText);
        }
        const redirectChain = httpRequest.redirectChain();
        if (redirectChain.length) {
            response.push(`### Redirect chain`);
            let indent = 0;
            for (const request of redirectChain.reverse()) {
                response.push(`${'  '.repeat(indent)}${getShortDescriptionForRequest(request, context.getNetworkRequestStableId(request))}`);
                indent++;
            }
        }
        return response;
    }
    resetResponseLineForTesting() {
        this.#textResponseLines = [];
    }
}
