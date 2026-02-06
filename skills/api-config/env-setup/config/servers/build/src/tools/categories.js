/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */
export var ToolCategory;
(function (ToolCategory) {
    ToolCategory["INPUT"] = "input";
    ToolCategory["NAVIGATION"] = "navigation";
    ToolCategory["EMULATION"] = "emulation";
    ToolCategory["PERFORMANCE"] = "performance";
    ToolCategory["NETWORK"] = "network";
    ToolCategory["DEBUGGING"] = "debugging";
})(ToolCategory || (ToolCategory = {}));
export const labels = {
    [ToolCategory.INPUT]: 'Input automation',
    [ToolCategory.NAVIGATION]: 'Navigation automation',
    [ToolCategory.EMULATION]: 'Emulation',
    [ToolCategory.PERFORMANCE]: 'Performance',
    [ToolCategory.NETWORK]: 'Network',
    [ToolCategory.DEBUGGING]: 'Debugging',
};
