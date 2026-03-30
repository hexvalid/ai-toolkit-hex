import fs from 'fs';
import path from 'path';
import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

type ContinueMode = 'resume' | 'clone';

function getJobConfig(jobConfigRaw: string) {
  return JSON.parse(jobConfigRaw);
}

function getLatestCheckpointPath(jobFolder: string, baseName: string): string | null {
  if (!fs.existsSync(jobFolder)) {
    return null;
  }

  const entries = fs.readdirSync(jobFolder);
  const checkpointCandidates = entries
    .filter(entry => entry.startsWith(baseName))
    .map(entry => path.join(jobFolder, entry))
    .filter(fullPath => {
      if (!fs.existsSync(fullPath)) {
        return false;
      }
      const stat = fs.statSync(fullPath);
      if (stat.isDirectory()) {
        return true;
      }
      return fullPath.endsWith('.safetensors') || fullPath.endsWith('.pt');
    });

  if (checkpointCandidates.length === 0) {
    return null;
  }

  const getSortKey = (candidatePath: string): [number, number, number] => {
    const basename = path.basename(candidatePath);
    const stepMatch = basename.match(/_(\d+)(?:\.(?:safetensors|pt))?$/);
    const modifiedTime = fs.statSync(candidatePath).mtimeMs;
    if (stepMatch) {
      return [1, parseInt(stepMatch[1], 10), modifiedTime];
    }
    return [2, 0, modifiedTime];
  };

  checkpointCandidates.sort((left, right) => {
    const leftKey = getSortKey(left);
    const rightKey = getSortKey(right);
    if (leftKey[0] !== rightKey[0]) {
      return rightKey[0] - leftKey[0];
    }
    if (leftKey[1] !== rightKey[1]) {
      return rightKey[1] - leftKey[1];
    }
    return rightKey[2] - leftKey[2];
  });

  return checkpointCandidates[0] ?? null;
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ jobID: string }> }) {
  const { jobID } = await params;
  const body = await request.json();
  const mode = body.mode as ContinueMode;
  const newSteps = typeof body.newSteps === 'number' ? body.newSteps : undefined;
  const newName = typeof body.newName === 'string' ? body.newName.trim() : undefined;

  if (mode !== 'resume' && mode !== 'clone') {
    return NextResponse.json({ error: 'Invalid mode' }, { status: 400 });
  }

  const job = await prisma.job.findUnique({
    where: { id: jobID },
  });

  if (!job) {
    return NextResponse.json({ error: 'Job not found' }, { status: 404 });
  }

  if (job.status !== 'completed') {
    return NextResponse.json({ error: 'Only completed jobs can be continued' }, { status: 400 });
  }

  try {
    const jobConfig = getJobConfig(job.job_config);
    const processConfig = jobConfig?.config?.process?.[0];

    if (!processConfig) {
      return NextResponse.json({ error: 'Job config is missing process[0]' }, { status: 400 });
    }

    if (mode === 'resume') {
      if (newSteps !== undefined && newSteps <= job.step) {
        return NextResponse.json({ error: 'New steps must be greater than current step' }, { status: 400 });
      }

      if (newSteps !== undefined) {
        processConfig.train.steps = newSteps;
      }

      if (processConfig.network?.pretrained_lora_path) {
        delete processConfig.network.pretrained_lora_path;
      }

      const updatedJob = await prisma.job.update({
        where: { id: jobID },
        data: {
          status: 'stopped',
          stop: false,
          return_to_queue: false,
          info: 'Ready to resume from latest checkpoint',
          job_config: JSON.stringify(jobConfig),
        },
      });

      return NextResponse.json(updatedJob);
    }

    const sourceName = jobConfig?.config?.name ?? job.name;
    const clonedName = newName && newName.length > 0 ? newName : `${sourceName}_continued`;
    if (newSteps !== undefined) {
      processConfig.train.steps = newSteps;
    }
    jobConfig.config.name = clonedName;

    const trainingFolder = processConfig.training_folder;
    const oldJobFolder = path.join(trainingFolder, sourceName);
    const latestCheckpoint = getLatestCheckpointPath(oldJobFolder, sourceName);

    if (processConfig.network && latestCheckpoint) {
      processConfig.network.pretrained_lora_path = latestCheckpoint;
    }

    const highestQueuePosition = await prisma.job.aggregate({
      _max: {
        queue_position: true,
      },
    });
    const newQueuePosition = (highestQueuePosition._max.queue_position || 0) + 1000;

    const newJob = await prisma.job.create({
      data: {
        name: clonedName,
        gpu_ids: job.gpu_ids,
        job_config: JSON.stringify(jobConfig),
        status: 'stopped',
        stop: false,
        return_to_queue: false,
        step: 0,
        info: latestCheckpoint
          ? `Ready to start from ${path.basename(latestCheckpoint)}`
          : 'Ready to start from copied config',
        queue_position: newQueuePosition,
      },
    });

    return NextResponse.json(newJob);
  } catch (error: any) {
    if (error.code === 'P2002') {
      return NextResponse.json({ error: 'Job name already exists' }, { status: 409 });
    }
    console.error('Error continuing job:', error);
    return NextResponse.json({ error: 'Failed to continue job' }, { status: 500 });
  }
}
