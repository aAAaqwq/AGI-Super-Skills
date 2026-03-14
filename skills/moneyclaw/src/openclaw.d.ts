declare module "openclaw/plugin-sdk" {
    export interface OpenClawPluginApi {
        pluginConfig: any;
        logger: {
            info: (msg: string) => void;
            warn: (msg: string) => void;
            error: (msg: string) => void;
        };
        registerTool: (params: {
            label: string;
            name: string;
            description: string;
            parameters: any;
            execute: (toolCallId: string, args: any) => Promise<any>;
        }) => void;
        registerService: (params: {
            id: string;
            start: () => void | Promise<void>;
            stop: () => void | Promise<void>;
        }) => void;
        on: (event: string, handler: (event: any) => Promise<any>) => void;
        runtime: {
            system: {
                enqueueSystemEvent: (message: string, context?: any) => void;
            }
        };
    }
}
