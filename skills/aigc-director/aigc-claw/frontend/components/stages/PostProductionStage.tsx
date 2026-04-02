'use client';

import React from 'react';
import { Download, Film } from 'lucide-react';
import type { StageViewProps } from './types';
import { assetUrl } from './utils';
import StageProgress from './StageProgress';
import StageActions from './StageActions';

export default function PostProductionStage({ state, onConfirm, onRegenerate, showConfirm, isRunning, hasPendingItems, hasNextStageStarted }: StageViewProps) {
  // payload: { session_id, final_video: "code/result/video/{sid}/{sid}_final.mp4" }
  const finalVideoPath: string = state.artifact?.final_video || '';
  const finalVideoUrl = assetUrl(finalVideoPath);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-1">后期剪辑</h2>
        <p className="text-sm text-gray-500 mb-6">拼接所有视频片段，合成最终成片</p>

        {/* 运行中 */}
        {state.status === 'running' && (
          <StageProgress message={state.progressMessage} fallback="正在合成最终视频..." progress={state.progress} color="cyan" />
        )}

        {state.error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 p-4 rounded-xl mb-4">{state.error}</div>
        )}

        {/* 最终视频 */}
        {finalVideoUrl && (
          <div className="space-y-4">
            <div className="bg-black rounded-xl overflow-hidden shadow-lg">
              <video src={finalVideoUrl} controls className="w-full max-h-[65vh]" />
            </div>
            <div className="flex items-center justify-center gap-3">
              <a
                href={finalVideoUrl}
                download
                className="flex items-center gap-2 px-5 py-2.5 bg-blue-500 text-white rounded-xl text-sm font-medium hover:bg-blue-600 transition-colors"
              >
                <Download className="w-4 h-4" />
                下载成片
              </a>
            </div>
          </div>
        )}

        {state.status === 'completed' && !finalVideoUrl && (
          <div className="flex flex-col items-center justify-center py-20 text-gray-400">
            <Film className="w-12 h-12 mb-3" />
            <div className="text-sm">视频合成完成</div>
          </div>
        )}

        {state.status === 'pending' && (
          <div className="text-center text-gray-400 text-sm py-20">等待上一阶段完成...</div>
        )}
      </div>

      <StageActions
        status={state.status}
        onConfirm={onConfirm}
        showConfirm={false}
        onRegenerate={onRegenerate}
        stageId="post_production"
        hasPendingItems={hasPendingItems}
        hasNextStageStarted={hasNextStageStarted}
        isRunning={isRunning}
      />
    </div>
  );
}
