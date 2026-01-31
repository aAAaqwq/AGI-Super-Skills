/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */
import { isUtf8 } from 'node:buffer';
const BODY_CONTEXT_SIZE_LIMIT = 10000;
export function getShortDescriptionForRequest(request, id, selectedInDevToolsUI = false) {
    // TODO truncate the URL
    return `reqid=${id} ${request.method()} ${request.url()} ${getStatusFromRequest(request)}${selectedInDevToolsUI ? ` [selected in the DevTools Network panel]` : ''}`;
}
export function getStatusFromRequest(request) {
    const httpResponse = request.response();
    const failure = request.failure();
    let status;
    if (httpResponse) {
        const responseStatus = httpResponse.status();
        status =
            responseStatus >= 200 && responseStatus <= 299
                ? `[success - ${responseStatus}]`
                : `[failed - ${responseStatus}]`;
    }
    else if (failure) {
        status = `[failed - ${failure.errorText}]`;
    }
    else {
        status = '[pending]';
    }
    return status;
}
export function getFormattedHeaderValue(headers) {
    const response = [];
    for (const [name, value] of Object.entries(headers)) {
        response.push(`- ${name}:${value}`);
    }
    return response;
}
export async function getFormattedResponseBody(httpResponse, sizeLimit = BODY_CONTEXT_SIZE_LIMIT) {
    try {
        const responseBuffer = await httpResponse.buffer();
        if (isUtf8(responseBuffer)) {
            const responseAsTest = responseBuffer.toString('utf-8');
            if (responseAsTest.length === 0) {
                return `<empty response>`;
            }
            return `${getSizeLimitedString(responseAsTest, sizeLimit)}`;
        }
        return `<binary data>`;
    }
    catch {
        return `<not available anymore>`;
    }
}
export async function getFormattedRequestBody(httpRequest, sizeLimit = BODY_CONTEXT_SIZE_LIMIT) {
    if (httpRequest.hasPostData()) {
        const data = httpRequest.postData();
        if (data) {
            return `${getSizeLimitedString(data, sizeLimit)}`;
        }
        try {
            const fetchData = await httpRequest.fetchPostData();
            if (fetchData) {
                return `${getSizeLimitedString(fetchData, sizeLimit)}`;
            }
        }
        catch {
            return `<not available anymore>`;
        }
    }
    return;
}
function getSizeLimitedString(text, sizeLimit) {
    if (text.length > sizeLimit) {
        return `${text.substring(0, sizeLimit) + '... <truncated>'}`;
    }
    return `${text}`;
}
