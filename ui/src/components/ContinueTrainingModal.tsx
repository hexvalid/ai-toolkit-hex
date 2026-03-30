'use client';

import React, { useEffect, useState } from 'react';
import { Job } from '@prisma/client';
import { Modal } from './Modal';
import { getJobConfig, getTotalSteps } from '@/utils/jobs';

interface ContinueTrainingModalProps {
  isOpen: boolean;
  onClose: () => void;
  job: Job;
  onContinue: (mode: 'resume' | 'clone', newSteps: number, newName?: string) => void;
}

export const ContinueTrainingModal: React.FC<ContinueTrainingModalProps> = ({
  isOpen,
  onClose,
  job,
  onContinue,
}) => {
  const jobConfig = getJobConfig(job);
  const processConfig = jobConfig.config.process[0];
  const hasNetworkConfig = !!processConfig.network;
  const currentSteps = getTotalSteps(job);
  const defaultNewSteps = Math.max(job.step + 1, currentSteps + 2000);
  const [mode, setMode] = useState<'resume' | 'clone'>('resume');
  const [newSteps, setNewSteps] = useState(defaultNewSteps);
  const [newName, setNewName] = useState(`${job.name}_continued`);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setMode('resume');
    setNewSteps(defaultNewSteps);
    setNewName(`${job.name}_continued`);
  }, [defaultNewSteps, isOpen, job.name]);

  const isResumeInvalid = mode === 'resume' && newSteps <= job.step;
  const isCloneInvalid = mode === 'clone' && newName.trim().length === 0;

  const handleContinue = () => {
    if (isResumeInvalid || isCloneInvalid) {
      return;
    }
    onContinue(mode, newSteps, mode === 'clone' ? newName.trim() : undefined);
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Continue Training" size="lg">
      <div className="space-y-6">
        <div className="space-y-3">
          <label className="block text-sm font-medium text-gray-200">Continue Mode</label>

          <div
            className={`cursor-pointer rounded-lg border-2 p-4 transition-colors ${
              mode === 'resume'
                ? 'border-blue-500 bg-blue-500/10'
                : 'border-gray-700 bg-gray-800 hover:border-gray-600'
            }`}
            onClick={() => setMode('resume')}
          >
            <div className="flex items-start">
              <input
                type="radio"
                name="mode"
                checked={mode === 'resume'}
                onChange={() => setMode('resume')}
                className="mt-1 h-4 w-4 text-blue-500"
              />
              <div className="ml-3">
                <h4 className="text-base font-semibold text-gray-100">Resume Training</h4>
                <p className="mt-1 text-sm text-gray-400">
                  Continue from the latest checkpoint with the same job name and step counter.
                </p>
                <div className="mt-2 text-xs text-gray-500">
                  Current progress: {job.step} / {currentSteps}
                </div>
              </div>
            </div>
          </div>

          <div
            className={`rounded-lg border-2 p-4 transition-colors ${
              hasNetworkConfig ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'
            } ${
              mode === 'clone'
                ? 'border-blue-500 bg-blue-500/10'
                : 'border-gray-700 bg-gray-800 hover:border-gray-600'
            }`}
            onClick={() => {
              if (hasNetworkConfig) {
                setMode('clone');
              }
            }}
          >
            <div className="flex items-start">
              <input
                type="radio"
                name="mode"
                checked={mode === 'clone'}
                onChange={() => {
                  if (hasNetworkConfig) {
                    setMode('clone');
                  }
                }}
                disabled={!hasNetworkConfig}
                className="mt-1 h-4 w-4 text-blue-500"
              />
              <div className="ml-3">
                <h4 className="text-base font-semibold text-gray-100">Start Fresh from Weights</h4>
                <p className="mt-1 text-sm text-gray-400">
                  Create a new job name and use the latest finished LoRA weights as the starting point.
                </p>
                <div className="mt-2 text-xs text-gray-500">
                  {hasNetworkConfig
                    ? 'Creates a new job with pretrained LoRA weights.'
                    : 'Unavailable for jobs without a network config.'}
                </div>
              </div>
            </div>
          </div>
        </div>

        {mode === 'clone' && (
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-200">New Job Name</label>
            <input
              type="text"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-gray-100 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter new job name"
            />
          </div>
        )}

        <div>
          <label className="mb-2 block text-sm font-medium text-gray-200">
            {mode === 'resume' ? 'New Total Steps' : 'Total Steps for New Job'}
          </label>
          <div className="flex items-center space-x-3">
            <input
              type="number"
              value={newSteps}
              onChange={e => setNewSteps(parseInt(e.target.value, 10) || 0)}
              className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-gray-100 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              min={mode === 'resume' ? job.step + 1 : 0}
            />
            <div className="text-sm text-gray-400">
              Current: {job.step} / {currentSteps}
            </div>
          </div>
          {isResumeInvalid && (
            <p className="mt-1 text-xs text-red-400">
              Steps must be greater than current step ({job.step}).
            </p>
          )}
          {isCloneInvalid && (
            <p className="mt-1 text-xs text-red-400">
              New job name is required.
            </p>
          )}
        </div>

        <div className="flex justify-end space-x-3 border-t border-gray-700 pt-4">
          <button
            onClick={onClose}
            className="rounded-lg border border-gray-600 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500"
          >
            Cancel
          </button>
          <button
            onClick={handleContinue}
            disabled={isResumeInvalid || isCloneInvalid}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {mode === 'resume' ? 'Resume Training' : 'Create & Start Later'}
          </button>
        </div>
      </div>
    </Modal>
  );
};
