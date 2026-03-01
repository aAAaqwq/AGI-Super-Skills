export function jsonResult(payload: any): any {
    return {
        content: [
            {
                type: "text",
                text: JSON.stringify(payload, null, 2),
            },
        ],
        details: payload,
    };
}
